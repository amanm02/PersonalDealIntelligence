"""One-shot local Banking MVP workflow runs."""

from __future__ import annotations

import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from pdi.public_pilot import (
    DEFAULT_PUBLIC_PILOT_CONFIG,
    PublicPilotCollectionError,
    run_public_pilot_workflow,
)
from pdi.smoke import (
    DEFAULT_ALERT_CONFIG,
    DEFAULT_AS_OF,
    DEFAULT_FIXTURE_DIR,
    run_offline_banking_smoke,
)
from pdi.storage import (
    acquire_banking_run_lock,
    get_banking_run,
    initialize_database,
    insert_banking_run,
    list_banking_score_records,
    release_banking_run_lock,
    update_banking_run,
)


DbPath = str | Path
DEFAULT_RUN_DIGEST_OUTPUT = Path("data/digests/banking_run_digest.md")


def run_banking_workflow_once(
    db_path: DbPath,
    *,
    dry_run: bool = True,
    sources: str = "demo",
    source_config_path: str | Path = DEFAULT_PUBLIC_PILOT_CONFIG,
    confirm_live: bool = False,
    fixture_dir: str | Path = DEFAULT_FIXTURE_DIR,
    digest_output: str | Path = DEFAULT_RUN_DIGEST_OUTPUT,
    alert_config_path: str | Path = DEFAULT_ALERT_CONFIG,
    as_of: date = DEFAULT_AS_OF,
) -> dict[str, Any]:
    """Run the selected local Banking MVP workflow once and record history."""

    initialize_database(db_path)
    metadata = _base_metadata(
        sources=sources,
        source_config_path=source_config_path,
        fixture_dir=fixture_dir,
        digest_output=digest_output,
        alert_config_path=alert_config_path,
    )
    run_id = insert_banking_run(
        db_path,
        dry_run=dry_run,
        metadata={**metadata, "digest_written": False},
    )

    lock_acquired = acquire_banking_run_lock(db_path, run_id)
    if not lock_acquired:
        update_banking_run(
            db_path,
            run_id,
            status="blocked",
            errors=["another banking run is already active"],
            metadata={
                **metadata,
                "blocked_by_existing_lock": True,
                "stale_lock_cleanup": "out_of_scope",
            },
        )
        return _run_payload(db_path, run_id)

    try:
        if sources == "public-pilot":
            summary = run_public_pilot_workflow(
                db_path,
                source_config_path=source_config_path,
                dry_run=dry_run,
                confirm_live=confirm_live,
                digest_output=digest_output,
                alert_config_path=alert_config_path,
                as_of=as_of,
                banking_run_id=None if dry_run else run_id,
            )
            update_banking_run(
                db_path,
                run_id,
                status="succeeded",
                counts=_run_counts_with_score_records(
                    db_path,
                    run_id,
                    summary,
                    dry_run=dry_run,
                ),
                digest_path=summary.get("digest_path"),
                metadata={
                    **metadata,
                    "digest_written": bool(summary.get("digest_path")) and not dry_run,
                    "public_pilot": {
                        "message": summary.get("message"),
                        "planned_sources": summary.get("planned_sources", []),
                        "enabled_source_count": summary.get("enabled_source_count", 0),
                        "network_fetch_attempted": summary.get(
                            "network_fetch_attempted",
                            False,
                        ),
                    },
                },
            )
        elif dry_run:
            summary = _run_dry_run_copy(
                db_path,
                fixture_dir=fixture_dir,
                alert_config_path=alert_config_path,
                as_of=as_of,
            )
            update_banking_run(
                db_path,
                run_id,
                status="succeeded",
                counts=_run_counts_with_score_records(
                    db_path,
                    run_id,
                    summary,
                    dry_run=True,
                ),
                metadata={
                    **metadata,
                    "dry_run_database": "temporary_copy",
                    "digest_written": False,
                    "would_be_digest_path": str(digest_output),
                },
            )
        elif sources == "demo":
            summary = run_offline_banking_smoke(
                db_path,
                fixture_dir=fixture_dir,
                digest_output=digest_output,
                alert_config_path=alert_config_path,
                as_of=as_of,
                allow_existing=True,
                banking_run_id=run_id,
            ).to_dict()
            update_banking_run(
                db_path,
                run_id,
                status="succeeded",
                counts=_run_counts_with_score_records(
                    db_path,
                    run_id,
                    summary,
                    dry_run=False,
                ),
                digest_path=str(summary["digest_path"]),
                metadata={**metadata, "digest_written": True},
            )
        else:
            raise ValueError(f"Unsupported banking run source group: {sources}")
    except Exception as error:  # pragma: no cover - exercised through callers.
        failure_metadata = {**metadata, "digest_written": False}
        if sources == "public-pilot" and isinstance(error, PublicPilotCollectionError):
            failure_metadata["public_pilot"] = {
                "message": str(error),
                "planned_sources": error.planned_sources,
                "enabled_source_count": error.enabled_source_count,
                "network_fetch_attempted": error.network_fetch_attempted,
            }
        update_banking_run(
            db_path,
            run_id,
            status="failed",
            counts=_run_counts_with_score_records(
                db_path,
                run_id,
                {},
                dry_run=dry_run,
            ),
            errors=[f"{type(error).__name__}: {error}"],
            metadata=failure_metadata,
        )
    finally:
        release_banking_run_lock(db_path, run_id=run_id)

    return _run_payload(db_path, run_id)


def _run_counts_with_score_records(
    db_path: DbPath,
    run_id: int,
    summary: dict[str, Any],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    if dry_run:
        return {
            **summary,
            "score_record_count": 0,
            "score_record_ids": [],
        }

    score_record_ids = [
        int(record["id"])
        for record in reversed(
            list_banking_score_records(db_path, banking_run_id=run_id)
        )
    ]
    return {
        **summary,
        "score_record_count": len(score_record_ids),
        "score_record_ids": score_record_ids,
    }


def _run_dry_run_copy(
    db_path: DbPath,
    *,
    fixture_dir: str | Path,
    alert_config_path: str | Path,
    as_of: date,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pdi-banking-dry-run-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_db = temp_root / "pdi-dry-run.sqlite"
        temp_digest = temp_root / "dry-run-digest.md"
        shutil.copy2(db_path, temp_db)
        return run_offline_banking_smoke(
            temp_db,
            fixture_dir=fixture_dir,
            digest_output=temp_digest,
            alert_config_path=alert_config_path,
            as_of=as_of,
            allow_existing=True,
        ).to_dict()


def _base_metadata(
    *,
    sources: str,
    source_config_path: str | Path,
    fixture_dir: str | Path,
    digest_output: str | Path,
    alert_config_path: str | Path,
) -> dict[str, Any]:
    return {
        "workflow": "public_pilot" if sources == "public-pilot" else "offline_fixture",
        "sources": sources,
        "source_config_path": str(source_config_path),
        "fixture_dir": str(fixture_dir),
        "alert_config_path": str(alert_config_path),
        "requested_digest_path": str(digest_output),
        "stale_lock_cleanup": "out_of_scope",
    }


def _run_payload(db_path: DbPath, run_id: int) -> dict[str, Any]:
    row = get_banking_run(db_path, run_id)
    if row is None:
        raise ValueError(f"Run id {run_id} does not exist.")
    return row

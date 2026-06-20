"""Offline fixture smoke flow for the Banking MVP."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

from pdi.alerts import (
    generate_banking_digest,
    load_alert_config,
    write_digest_artifact,
)
from pdi.collectors import ManualTextCollector, persist_collected_snapshot
from pdi.dedupe import canonicalize_pending_candidates
from pdi.extractors import extract_and_persist_snapshot
from pdi.scoring import persist_banking_deal_score
from pdi.sources import SourcePolicy
from pdi.storage import (
    initialize_database,
    insert_source_record,
    list_banking_deal_candidates,
    list_banking_deals,
    list_deal_change_events,
)


DbPath = str | Path
DEFAULT_FIXTURE_DIR = Path("examples/offline_smoke")
DEFAULT_ALERT_CONFIG = Path("config/banking_alerts.yaml")
DEFAULT_DIGEST_OUTPUT = Path("data/digests/offline_smoke_digest.md")
DEFAULT_AS_OF = date(2026, 6, 18)
RETRIEVED_AT = "2026-06-18T12:00:00+00:00"


@dataclass(frozen=True)
class SmokeFixture:
    """One offline fixture source used by the smoke flow."""

    fixture_id: str
    source_name: str
    source_url: str
    source_type: str
    subcategory: str
    fixture_path: Path


@dataclass(frozen=True)
class OfflineSmokeSummary:
    """Counts and artifact paths from one offline smoke run."""

    sources: int
    raw_snapshots: int
    candidates: int
    rejected_candidates: int
    canonical_deals: int
    duplicate_merges: int
    conflicts: int
    review_needed_deals: int
    scored_deals: int
    expired_scored_deals: int
    digest_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": self.sources,
            "raw_snapshots": self.raw_snapshots,
            "candidates": self.candidates,
            "rejected_candidates": self.rejected_candidates,
            "canonical_deals": self.canonical_deals,
            "duplicate_merges": self.duplicate_merges,
            "conflicts": self.conflicts,
            "review_needed_deals": self.review_needed_deals,
            "scored_deals": self.scored_deals,
            "expired_scored_deals": self.expired_scored_deals,
            "digest_path": self.digest_path,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


class SmokeRunError(ValueError):
    """Raised when an offline smoke run cannot be started safely."""


def load_smoke_fixtures(fixture_dir: str | Path = DEFAULT_FIXTURE_DIR) -> list[SmokeFixture]:
    """Load the deterministic offline smoke fixture manifest."""

    root = Path(fixture_dir)
    manifest_path = root / "manifest.yaml"
    raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw_manifest, Mapping):
        raise SmokeRunError("offline smoke manifest must be a mapping")
    raw_fixtures = raw_manifest.get("fixtures")
    if not isinstance(raw_fixtures, list) or not raw_fixtures:
        raise SmokeRunError("offline smoke manifest requires a non-empty fixtures list")

    fixtures: list[SmokeFixture] = []
    for index, raw_fixture in enumerate(raw_fixtures):
        if not isinstance(raw_fixture, Mapping):
            raise SmokeRunError(f"fixture {index} must be a mapping")
        required = {
            "id",
            "source_name",
            "source_url",
            "source_type",
            "subcategory",
            "fixture_path",
        }
        missing = required - set(raw_fixture)
        if missing:
            raise SmokeRunError(
                f"fixture {index} missing required fields: {', '.join(sorted(missing))}"
            )
        fixture_path = root / str(raw_fixture["fixture_path"])
        if not fixture_path.exists():
            raise SmokeRunError(f"fixture file does not exist: {fixture_path}")
        fixtures.append(
            SmokeFixture(
                fixture_id=str(raw_fixture["id"]),
                source_name=str(raw_fixture["source_name"]),
                source_url=str(raw_fixture["source_url"]),
                source_type=str(raw_fixture["source_type"]),
                subcategory=str(raw_fixture["subcategory"]),
                fixture_path=fixture_path,
            )
        )
    return fixtures


def run_offline_banking_smoke(
    db_path: DbPath,
    *,
    fixture_dir: str | Path = DEFAULT_FIXTURE_DIR,
    digest_output: str | Path = DEFAULT_DIGEST_OUTPUT,
    alert_config_path: str | Path = DEFAULT_ALERT_CONFIG,
    as_of: date = DEFAULT_AS_OF,
    reset_db: bool = False,
) -> OfflineSmokeSummary:
    """Run the full Banking MVP flow against local text fixtures only."""

    db_file = Path(db_path)
    if db_file.exists():
        if not reset_db:
            raise SmokeRunError(
                f"database already exists: {db_file}; pass --reset-db to replace it"
            )
        if not db_file.is_file():
            raise SmokeRunError(f"database path exists but is not a file: {db_file}")
        db_file.unlink()

    fixtures = load_smoke_fixtures(fixture_dir)
    initialize_database(db_file)

    collector = ManualTextCollector()
    source_count = 0
    snapshot_ids: list[int] = []
    candidate_ids: list[int] = []

    for fixture in fixtures:
        source_policy = _source_policy(fixture)
        source_record_id = insert_source_record(
            db_file,
            {
                "source_name": fixture.source_name,
                "source_url": fixture.source_url,
                "source_type": fixture.source_type,
                "collection_method": "manual_only",
                "enabled": True,
                "max_frequency": "manual_only",
                "compliance_notes": "Offline smoke fixture; no network access.",
            },
        )
        source_count += 1
        snapshot = collector.collect(
            source_policy,
            fixture_path=fixture.fixture_path,
            retrieved_at=RETRIEVED_AT,
            raw_payload={"fixture_id": fixture.fixture_id},
        )
        snapshot_id = persist_collected_snapshot(
            db_file,
            snapshot,
            source_record_id=source_record_id,
        )
        snapshot_ids.append(snapshot_id)
        candidate_ids.append(extract_and_persist_snapshot(db_file, snapshot_id))

    canonicalization_results = canonicalize_pending_candidates(db_file)
    scores = [
        persist_banking_deal_score(db_file, int(deal["id"]), as_of=as_of)
        for deal in list_banking_deals(db_file)
    ]

    digest = generate_banking_digest(db_file, config_path=alert_config_path, as_of=as_of)
    digest_path = write_digest_artifact(
        digest,
        digest_output,
        output_format="markdown",
        minimum_hours_between_digests=0,
        force=True,
    )

    candidates = list_banking_deal_candidates(db_file)
    deals = list_banking_deals(db_file)
    return OfflineSmokeSummary(
        sources=source_count,
        raw_snapshots=len(snapshot_ids),
        candidates=len(candidate_ids),
        rejected_candidates=sum(1 for candidate in candidates if candidate["rejected"]),
        canonical_deals=len(deals),
        duplicate_merges=sum(
            1
            for result in canonicalization_results
            if result.action in {"matched", "updated"}
        ),
        conflicts=sum(1 for result in canonicalization_results if result.conflict_fields),
        review_needed_deals=sum(1 for deal in deals if deal["status"] == "needs_review"),
        scored_deals=len(scores),
        expired_scored_deals=sum(
            1 for score in scores if score.recommended_action == "expired"
        ),
        digest_path=str(digest_path),
    )


def _source_policy(fixture: SmokeFixture) -> SourcePolicy:
    return SourcePolicy(
        name=fixture.source_name,
        url=fixture.source_url,
        source_type=fixture.source_type,
        category_scope=("banking",),
        subcategory_scope=(fixture.subcategory,),
        enabled=True,
        collection_method="manual_only",
        max_frequency_hours=0,
        requires_login=False,
        allow_scrape=False,
        allow_api=False,
        allow_rss=False,
        allow_email_parse=False,
        robots_policy_notes="No network access; local fixture only.",
        terms_policy_notes="Synthetic offline fixture.",
        rate_limit_notes="Manual fixture only.",
        compliance_status="approved",
        last_reviewed_at=DEFAULT_AS_OF,
        notes="Used by the offline Banking MVP smoke test.",
    )

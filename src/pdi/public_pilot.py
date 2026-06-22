"""Opt-in public-pilot collection path for Banking MVP sources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from pdi.alerts import generate_banking_digest, write_digest_artifact
from pdi.collectors import RssCollector, persist_collected_snapshot
from pdi.dedupe import canonicalize_pending_candidates
from pdi.extractors import extract_and_persist_snapshot
from pdi.fetchers import SafeFetchResult, safe_fetch_public_source
from pdi.scoring import persist_banking_deal_score
from pdi.smoke import DEFAULT_ALERT_CONFIG, DEFAULT_AS_OF
from pdi.sources import SourcePolicy, load_source_policies
from pdi.storage import (
    initialize_database,
    insert_source_record,
    list_banking_deal_candidates,
    list_banking_deals,
)


DbPath = str | Path
PublicPilotFetcher = Callable[[SourcePolicy], SafeFetchResult]
PUBLIC_PILOT_GROUP = "public-pilot"
NO_ENABLED_PUBLIC_PILOT_MESSAGE = "No enabled public pilot sources configured."
DEFAULT_PUBLIC_PILOT_CONFIG = Path("config/banking_sources.yaml")
DEFAULT_PUBLIC_PILOT_DIGEST_OUTPUT = Path("data/digests/public_pilot_digest.md")
DEFAULT_RETRIEVED_AT = "2026-06-21T12:00:00+00:00"


class PublicPilotCollectionError(ValueError):
    """Raised for fail-closed public-pilot collection errors."""

    def __init__(
        self,
        message: str,
        *,
        planned_sources: list[dict[str, Any]],
        enabled_source_count: int,
        network_fetch_attempted: bool,
    ) -> None:
        self.planned_sources = planned_sources
        self.enabled_source_count = enabled_source_count
        self.network_fetch_attempted = network_fetch_attempted
        super().__init__(message)


def list_public_pilot_sources(
    config_path: str | Path = DEFAULT_PUBLIC_PILOT_CONFIG,
    *,
    source_group: str | None = None,
) -> list[dict[str, Any]]:
    """Return source policy summaries suitable for CLI display."""

    policies = load_source_policies(config_path)
    if source_group is not None:
        policies = [policy for policy in policies if policy.source_group == source_group]
    return [_source_summary(policy) for policy in policies]


def validate_public_pilot_sources(
    config_path: str | Path = DEFAULT_PUBLIC_PILOT_CONFIG,
) -> dict[str, Any]:
    """Validate configured source policies and summarize public-pilot readiness."""

    policies = load_source_policies(config_path)
    public_pilot = [
        policy for policy in policies if policy.source_group == PUBLIC_PILOT_GROUP
    ]
    return {
        "config_path": str(config_path),
        "source_count": len(policies),
        "public_pilot_source_count": len(public_pilot),
        "enabled_public_pilot_source_count": sum(
            1 for policy in public_pilot if policy.enabled
        ),
        "status": "valid",
    }


def run_public_pilot_workflow(
    db_path: DbPath,
    *,
    source_config_path: str | Path = DEFAULT_PUBLIC_PILOT_CONFIG,
    dry_run: bool,
    confirm_live: bool = False,
    fixture_dir: str | Path | None = None,
    fetcher: PublicPilotFetcher | None = None,
    digest_output: str | Path = DEFAULT_PUBLIC_PILOT_DIGEST_OUTPUT,
    alert_config_path: str | Path = DEFAULT_ALERT_CONFIG,
    as_of: date = DEFAULT_AS_OF,
    banking_run_id: int | None = None,
) -> dict[str, Any]:
    """Plan or execute public-pilot collection behind explicit source policy."""

    policies = [
        policy
        for policy in load_source_policies(source_config_path)
        if policy.source_group == PUBLIC_PILOT_GROUP
    ]
    enabled_policies = [policy for policy in policies if policy.enabled]
    planned_sources = [_source_summary(policy, dry_run=dry_run) for policy in policies]

    if dry_run:
        return _empty_summary(
            planned_sources=planned_sources,
            enabled_source_count=len(enabled_policies),
            message=(
                NO_ENABLED_PUBLIC_PILOT_MESSAGE if not enabled_policies else None
            ),
        )

    if not confirm_live:
        raise ValueError("Public pilot live collection requires --confirm-live or use --dry-run.")

    if not enabled_policies:
        return _empty_summary(
            planned_sources=planned_sources,
            enabled_source_count=0,
            message=NO_ENABLED_PUBLIC_PILOT_MESSAGE,
        )

    unsupported = [
        policy.source_id
        for policy in enabled_policies
        if _blocked_reason(policy) is not None
    ]
    if unsupported:
        raise PublicPilotCollectionError(
            "Public pilot live collection is blocked by source policy: "
            + ", ".join(sorted(unsupported)),
            planned_sources=planned_sources,
            enabled_source_count=len(enabled_policies),
            network_fetch_attempted=False,
        )

    initialize_database(db_path)
    fixture_map = _load_fixture_map(fixture_dir)
    collector = RssCollector()
    source_count = 0
    snapshot_ids: list[int] = []
    candidate_ids: list[int] = []
    network_fetch_attempted = False

    for policy in enabled_policies:
        source_record_id = insert_source_record(
            db_path,
            {
                "source_name": policy.name,
                "source_url": policy.url,
                "source_type": policy.source_type,
                "collection_method": policy.collection_method,
                "enabled": policy.enabled,
                "max_frequency": f"{policy.max_frequency_hours}h",
                "compliance_notes": policy.terms_policy_notes,
            },
        )
        source_count += 1

        fixture_path = fixture_map.get(policy.source_id)
        raw_text: str | None = None
        if fixture_path is None:
            network_fetch_attempted = True
            fetch_result = fetcher(policy) if fetcher else _fetch_public_rss(policy)
            _update_source_fetch_metadata(planned_sources, policy, fetch_result)
            if not fetch_result.ok or fetch_result.body_text is None:
                raise PublicPilotCollectionError(
                    _fetch_failure_message(policy, fetch_result),
                    planned_sources=planned_sources,
                    enabled_source_count=len(enabled_policies),
                    network_fetch_attempted=network_fetch_attempted,
                )
            raw_text = fetch_result.body_text

        snapshots = collector.collect(
            policy,
            raw_text=raw_text,
            fixture_path=fixture_path,
            retrieved_at=DEFAULT_RETRIEVED_AT,
        )
        for snapshot in snapshots:
            snapshot_id = persist_collected_snapshot(
                db_path,
                snapshot,
                source_record_id=source_record_id,
            )
            snapshot_ids.append(snapshot_id)
            candidate_ids.append(extract_and_persist_snapshot(db_path, snapshot_id))

    canonicalization_results = canonicalize_pending_candidates(db_path)
    scores = [
        persist_banking_deal_score(
            db_path,
            int(deal["id"]),
            as_of=as_of,
            banking_run_id=banking_run_id,
        )
        for deal in list_banking_deals(db_path)
    ]
    digest = generate_banking_digest(db_path, config_path=alert_config_path, as_of=as_of)
    digest_path = write_digest_artifact(
        digest,
        digest_output,
        output_format="markdown",
        minimum_hours_between_digests=0,
        force=True,
    )
    candidates = list_banking_deal_candidates(db_path)
    deals = list_banking_deals(db_path)
    return {
        "sources": source_count,
        "raw_snapshots": len(snapshot_ids),
        "candidates": len(candidate_ids),
        "rejected_candidates": sum(
            1 for candidate in candidates if candidate["rejected"]
        ),
        "canonical_deals": len(deals),
        "duplicate_merges": sum(
            1
            for result in canonicalization_results
            if result.action in {"matched", "updated"}
        ),
        "conflicts": sum(
            1 for result in canonicalization_results if result.conflict_fields
        ),
        "review_needed_deals": sum(
            1 for deal in deals if deal["status"] == "needs_review"
        ),
        "scored_deals": len(scores),
        "expired_scored_deals": sum(
            1 for score in scores if score.recommended_action == "expired"
        ),
        "digest_path": str(digest_path),
        "message": None,
        "planned_sources": planned_sources,
        "enabled_source_count": len(enabled_policies),
        "network_fetch_attempted": network_fetch_attempted,
    }


def _source_summary(policy: SourcePolicy, *, dry_run: bool = False) -> dict[str, Any]:
    blocked_reason = _blocked_reason(policy)
    eligibility_status = _eligibility_status(policy)
    collection_status = (
        "skipped_due_to_dry_run"
        if dry_run and blocked_reason is None
        else eligibility_status
    )
    return {
        "source_id": policy.source_id,
        "source_group": policy.source_group,
        "publisher_name": policy.publisher_name,
        "name": policy.name,
        "source_type": policy.source_type,
        "source_class": policy.source_class,
        "trust_tier": policy.trust_tier,
        "official_source": policy.official_source,
        "deposit_account_source": policy.deposit_account_source,
        "brokerage_source": policy.brokerage_source,
        "credit_card_source": policy.credit_card_source,
        "fixture_enabled": policy.fixture_enabled,
        "source_priority": policy.source_priority,
        "collection_method": policy.collection_method,
        "enabled": policy.enabled,
        "requires_login": policy.requires_login,
        "max_frequency_hours": policy.max_frequency_hours,
        "compliance_status": policy.compliance_status,
        "last_reviewed_at": policy.last_reviewed_at.isoformat(),
        "safety_state": "ready" if blocked_reason is None else "blocked",
        "blocked_reason": blocked_reason,
        "eligibility_status": eligibility_status,
        "collection_status": collection_status,
        "fetch_result": None,
    }


def _blocked_reason(policy: SourcePolicy) -> str | None:
    if not policy.enabled:
        return "disabled"
    if policy.requires_login:
        return "requires_login"
    if policy.compliance_status != "approved":
        return "compliance_status_not_approved"
    if policy.source_group == PUBLIC_PILOT_GROUP and policy.collection_method != "rss_feed":
        return "unsupported_public_pilot_method"
    return None


def _eligibility_status(policy: SourcePolicy) -> str:
    if not policy.enabled:
        return "disabled"
    if policy.requires_login:
        return "requires_login"
    if policy.compliance_status == "pending_review":
        return "pending_review"
    if policy.compliance_status != "approved":
        return "not_approved"
    if policy.source_group == PUBLIC_PILOT_GROUP and policy.collection_method != "rss_feed":
        return "unsupported_method"
    return "eligible"


def _update_source_fetch_metadata(
    planned_sources: list[dict[str, Any]],
    policy: SourcePolicy,
    fetch_result: SafeFetchResult,
) -> None:
    for source in planned_sources:
        if source["source_id"] == policy.source_id:
            source["collection_status"] = (
                "fetch_succeeded" if fetch_result.ok else "fetch_failed"
            )
            source["fetch_result"] = fetch_result.to_metadata()
            return


def _fetch_failure_message(
    policy: SourcePolicy,
    fetch_result: SafeFetchResult,
) -> str:
    error_type = fetch_result.error_type or "fetch_failed"
    error_message = fetch_result.error_message or "public-pilot fetch failed"
    return f"{policy.source_id}: {error_type}: {error_message}"


def _empty_summary(
    *,
    planned_sources: list[dict[str, Any]],
    enabled_source_count: int,
    message: str | None,
) -> dict[str, Any]:
    return {
        "sources": 0,
        "raw_snapshots": 0,
        "candidates": 0,
        "rejected_candidates": 0,
        "canonical_deals": 0,
        "duplicate_merges": 0,
        "conflicts": 0,
        "review_needed_deals": 0,
        "scored_deals": 0,
        "expired_scored_deals": 0,
        "digest_path": None,
        "message": message,
        "planned_sources": planned_sources,
        "enabled_source_count": enabled_source_count,
        "network_fetch_attempted": False,
    }


def _load_fixture_map(fixture_dir: str | Path | None) -> dict[str, Path]:
    if fixture_dir is None:
        return {}
    root = Path(fixture_dir)
    manifest_path = root / "manifest.yaml"
    raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    raw_sources = raw_manifest.get("sources") if isinstance(raw_manifest, dict) else None
    if not isinstance(raw_sources, list):
        raise ValueError("public-pilot manifest requires a sources list")
    fixtures: dict[str, Path] = {}
    for index, raw_source in enumerate(raw_sources):
        if not isinstance(raw_source, dict):
            raise ValueError(f"public-pilot fixture {index} must be a mapping")
        source_id = raw_source.get("source_id")
        fixture_path = raw_source.get("fixture_path")
        if not isinstance(source_id, str) or not isinstance(fixture_path, str):
            raise ValueError(
                f"public-pilot fixture {index} requires source_id and fixture_path"
            )
        path = root / fixture_path
        if not path.exists():
            raise ValueError(f"public-pilot fixture file does not exist: {path}")
        fixtures[source_id] = path
    return fixtures


def _fetch_public_rss(policy: SourcePolicy) -> SafeFetchResult:
    return safe_fetch_public_source(policy)

"""Offline QA benchmark for the Banking MVP demo corpus."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from pdi.demo_corpus import (
    DEFAULT_DEMO_DIR,
    DEFAULT_DEMO_SOURCE_CONFIG,
    DEMO_RETRIEVED_AT,
    load_demo_fixtures,
    persist_demo_snapshots,
)
from pdi.dedupe import CanonicalizationResult, canonicalize_pending_candidates
from pdi.extractors import extract_and_persist_snapshot
from pdi.scoring import BankingScore, persist_banking_deal_score
from pdi.storage import (
    initialize_database,
    list_banking_deal_candidates,
    list_banking_deals,
    list_deal_change_events,
)


DbPath = str | Path
DEFAULT_BENCHMARK_AS_OF = date(2026, 6, 18)
BENCHMARK_CATEGORIES = ("all", "deposit", "credit_card")
EXPECTED_DEPOSIT_DEALS = (
    "Cypress Sample Bank",
    "Harbor Demo Brokerage",
    "Lakeside Sample Bank",
    "Northstar Demo Bank",
    "Pioneer Example Bank",
    "Prairie Example Bank",
    "Riverbend Demo Bank",
    "Sunset Demo Bank",
)
EXPECTED_SUBCATEGORIES = (
    "checking_bonus",
    "savings_bonus",
    "checking_savings_bundle",
    "brokerage_bonus",
    "cd_bonus",
)
EXPECTED_EDGE_CASES = (
    "direct_deposit_required",
    "official_source",
    "minimum_balance_hold",
    "bundle_bonus",
    "tiered_bonus",
    "money_market_or_cd_bonus",
    "duplicate_offer",
    "expired_offer",
    "conflicting_terms",
    "low_value_offer",
    "missing_high_impact_terms",
    "non_deal_content",
    "disabled_or_disallowed_source",
)
FUTURE_DEPENDENCY_SECTIONS = (
    (
        "evidence_links",
        "#30",
        "evidence_model_deferred",
        "Evidence-link expansion remains deferred to #30.",
    ),
    (
        "persistence_tables",
        "#35",
        "persistence_expansion_deferred",
        "Candidate/source-link/score/run-history table expansion remains deferred to #35.",
    ),
    (
        "taxonomy_lifecycle",
        "#36",
        "taxonomy_lifecycle_deferred",
        "Canonical product taxonomy and offer lifecycle checks remain deferred to #36.",
    ),
    (
        "rules_engine",
        "#37",
        "rules_engine_deferred",
        "Eligibility and requirements rules-engine checks remain deferred to #37.",
    ),
    (
        "credit_card_model",
        "#40",
        "credit_card_model_parent_deferred",
        "Broad credit-card model checks remain deferred to #40 child issues.",
    ),
    (
        "credit_card_runtime_coverage",
        "#76",
        "credit_card_runtime_coverage_skipped_dependency",
        "Credit-card QA benchmark runtime coverage remains deferred to #76.",
    ),
)


class QaBenchmarkError(ValueError):
    """Raised when the offline QA benchmark cannot run safely."""


def run_banking_qa_benchmark(
    db_path: DbPath,
    *,
    category: str = "all",
    demo_dir: str | Path = DEFAULT_DEMO_DIR,
    source_config: str | Path = DEFAULT_DEMO_SOURCE_CONFIG,
    as_of: date = DEFAULT_BENCHMARK_AS_OF,
    reset_db: bool = False,
    allow_existing: bool = False,
    expected_deposit_deals: Sequence[str] = EXPECTED_DEPOSIT_DEALS,
) -> dict[str, Any]:
    """Run deterministic offline QA checks against the demo banking corpus."""

    if category not in BENCHMARK_CATEGORIES:
        raise QaBenchmarkError(
            f"category must be one of {', '.join(BENCHMARK_CATEGORIES)}"
        )

    db_file = Path(db_path)
    if db_file.exists():
        if not db_file.is_file():
            raise QaBenchmarkError(f"database path exists but is not a file: {db_file}")
        if reset_db:
            db_file.unlink()

    fixtures = load_demo_fixtures(demo_dir)
    initialize_database(db_file)
    seed_corpus = category in {"all", "deposit"} and not _has_existing_rows(db_file)

    snapshot_ids: list[int] = []
    candidate_ids: list[int] = []
    canonicalization_results: list[CanonicalizationResult] = []
    scores: dict[int, BankingScore] = {}

    if seed_corpus:
        snapshot_ids = persist_demo_snapshots(
            db_file,
            demo_dir=demo_dir,
            source_config=source_config,
            retrieved_at=DEMO_RETRIEVED_AT,
        )
        candidate_ids = [
            extract_and_persist_snapshot(db_file, snapshot_id)
            for snapshot_id in snapshot_ids
        ]
        canonicalization_results = canonicalize_pending_candidates(db_file)
        scores = {
            int(deal["id"]): persist_banking_deal_score(
                db_file,
                int(deal["id"]),
                as_of=as_of,
            )
            for deal in list_banking_deals(db_file)
        }
    elif category in {"all", "deposit"}:
        scores = {
            int(deal["id"]): persist_banking_deal_score(
                db_file,
                int(deal["id"]),
                as_of=as_of,
            )
            for deal in list_banking_deals(db_file)
        }

    candidates = list_banking_deal_candidates(db_file)
    deals = list_banking_deals(db_file)
    duplicate_merges = _duplicate_merge_count(
        candidates,
        deals,
        canonicalization_results,
    )
    conflicts = _conflict_count(db_file, canonicalization_results)
    failures: list[str] = []
    sections: dict[str, Any] = {}

    if category in {"all", "deposit"}:
        sections["deposit"] = _evaluate_deposit_benchmark(
            deals=deals,
            candidates=candidates,
            canonicalization_results=canonicalization_results,
            scores=scores,
            expected_deals=expected_deposit_deals,
            duplicate_merges=duplicate_merges,
            conflicts=conflicts,
        )
        failures.extend(sections["deposit"]["failures"])

    if category in {"all", "credit_card"}:
        sections["credit_card"] = _credit_card_pending_section()

    if category == "all":
        sections.update(_future_dependency_sections())

    status = "fail" if failures else "pass"
    if category == "credit_card":
        status = "pending"

    return {
        "benchmark": "banking_demo_qa",
        "verification_status": status,
        "category": category,
        "offline_only": True,
        "as_of": as_of.isoformat(),
        "inputs": {
            "demo_dir": str(demo_dir),
            "source_config": str(source_config),
            "retrieved_at": DEMO_RETRIEVED_AT,
        },
        "summary": {
            "fixtures": len(fixtures),
            "collectable_fixtures": sum(1 for fixture in fixtures if fixture.collect),
            "raw_snapshots": len(snapshot_ids) or _table_count(
                db_file,
                "raw_deal_snapshots",
            ),
            "candidates": len(candidate_ids) or len(candidates),
            "rejected_candidates": sum(
                1 for candidate in candidates if candidate["rejected"]
            ),
            "canonical_deals": len(deals),
            "duplicate_merges": duplicate_merges,
            "conflicts": conflicts,
            "scored_deals": len(scores),
        },
        "fixture_coverage": _fixture_coverage(fixtures),
        "sections": sections,
        "failures": failures,
    }


def _evaluate_deposit_benchmark(
    *,
    deals: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    canonicalization_results: Sequence[CanonicalizationResult],
    scores: Mapping[int, BankingScore],
    expected_deals: Sequence[str],
    duplicate_merges: int,
    conflicts: int,
) -> dict[str, Any]:
    found_names = sorted({str(deal["institution_name"]) for deal in deals})
    expected_names = sorted(expected_deals)
    missed = [name for name in expected_names if name not in found_names]
    unexpected = [name for name in found_names if name not in expected_names]
    subcategories = sorted({str(deal["subcategory"]) for deal in deals})

    northstar_deals = [
        deal for deal in deals if deal["institution_name"] == "Northstar Demo Bank"
    ]
    rejected_candidates = [candidate for candidate in candidates if candidate["rejected"]]
    non_deal_rejected = any(
        candidate["source_name"] == "Demo Manual User Pasted Banking Notes"
        and "No explicit banking promotion terms found"
        in str(candidate["rejection_reason"])
        for candidate in rejected_candidates
    )
    score_checks = _score_sanity_checks(deals, scores)
    checks = {
        "expected_deals_found": not missed,
        "unexpected_deals_absent": not unexpected,
        "expected_subcategories_present": set(EXPECTED_SUBCATEGORIES).issubset(
            subcategories
        ),
        "duplicate_offer_merged": len(northstar_deals) == 1 and duplicate_merges >= 1,
        "conflicting_terms_surfaced": bool(northstar_deals)
        and northstar_deals[0]["status"] == "needs_review"
        and conflicts >= 1,
        "non_deal_suppressed": len(rejected_candidates) == 1 and non_deal_rejected,
        "expired_offer_flagged": score_checks["expired_offer_flagged"],
        "low_value_offer_flagged": score_checks["low_value_offer_flagged"],
        "ambiguous_terms_surfaced": any(
            deal["institution_name"] == "Prairie Example Bank"
            and deal["bonus_amount_cents"] is None
            and deal["expires_at"] is None
            for deal in deals
        ),
        "scores_persisted": all(
            deal["estimated_net_value_cents"] is not None for deal in deals
        ),
    }
    failures = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    return {
        "status": "fail" if failures else "pass",
        "reason_code": "deposit_checks_failed" if failures else "supported_checks_passed",
        "reason": (
            "Supported deposit and brokerage QA checks failed."
            if failures
            else "Supported deposit and brokerage QA checks passed."
        ),
        "product_scope": "deposit, savings, bundle, brokerage, CD, and money-market banking fixtures",
        "expected_deals": expected_names,
        "expected_deals_found": len(expected_names) - len(missed),
        "expected_deals_missed": missed,
        "unexpected_deals": unexpected,
        "subcategories_found": subcategories,
        "checks": checks,
        "score_sanity": score_checks,
        "failures": failures,
    }


def _score_sanity_checks(
    deals: Sequence[Mapping[str, Any]],
    scores: Mapping[int, BankingScore],
) -> dict[str, Any]:
    by_name = {
        str(deal["institution_name"]): scores.get(int(deal["id"]))
        for deal in deals
    }
    sunset = by_name.get("Sunset Demo Bank")
    lakeside = by_name.get("Lakeside Sample Bank")
    northstar = by_name.get("Northstar Demo Bank")

    return {
        "expired_offer_flagged": sunset is not None
        and sunset.recommended_action == "expired",
        "low_value_offer_flagged": lakeside is not None
        and lakeside.recommended_action == "skip_low_value",
        "conflict_requires_review": northstar is not None
        and northstar.recommended_action == "conflict_needs_review",
        "score_bands": {
            name: score.score_band
            for name, score in sorted(by_name.items())
            if score is not None
        },
        "recommended_actions": {
            name: score.recommended_action
            for name, score in sorted(by_name.items())
            if score is not None
        },
    }


def _credit_card_pending_section() -> dict[str, Any]:
    return {
        "status": "pending_runtime",
        "reason_code": "credit_card_coverage_deferred_to_24d",
        "expected_deals_found": 0,
        "expected_deals_missed": [],
        "reason": (
            "Credit-card source and runtime display support exists, but QA "
            "benchmark coverage is intentionally deferred to #76 / 24D."
        ),
        "failures": [],
    }


def _future_dependency_sections() -> dict[str, dict[str, Any]]:
    return {
        section_name: {
            "status": "skipped_dependency",
            "reason_code": reason_code,
            "dependency": dependency,
            "reason": reason,
            "failures": [],
        }
        for section_name, dependency, reason_code, reason in FUTURE_DEPENDENCY_SECTIONS
    }


def _fixture_coverage(fixtures: Sequence[Any]) -> dict[str, Any]:
    edge_case_counts = {edge_case: 0 for edge_case in EXPECTED_EDGE_CASES}
    for fixture in fixtures:
        for edge_case in fixture.edge_cases:
            edge_case_counts.setdefault(edge_case, 0)
            edge_case_counts[edge_case] += 1
    missing_edge_cases = [
        edge_case
        for edge_case, count in sorted(edge_case_counts.items())
        if count == 0
    ]
    return {
        "edge_case_counts": dict(sorted(edge_case_counts.items())),
        "missing_edge_cases": missing_edge_cases,
        "disabled_fixture_count": sum(1 for fixture in fixtures if not fixture.collect),
    }


def _has_existing_rows(db_path: Path) -> bool:
    return any(
        _table_count(db_path, table_name) > 0
        for table_name in (
            "raw_deal_snapshots",
            "banking_deal_candidates",
            "banking_deals",
        )
    )


def _table_count(db_path: Path, table_name: str) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(
            connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        )


def _duplicate_merge_count(
    candidates: Sequence[Mapping[str, Any]],
    deals: Sequence[Mapping[str, Any]],
    canonicalization_results: Sequence[CanonicalizationResult],
) -> int:
    canonicalized_merges = sum(
        1
        for result in canonicalization_results
        if result.action in {"matched", "updated"}
    )
    if canonicalized_merges:
        return canonicalized_merges

    non_rejected_candidates = sum(
        1 for candidate in candidates if not candidate["rejected"]
    )
    return max(0, non_rejected_candidates - len(deals))


def _conflict_count(
    db_path: Path,
    canonicalization_results: Sequence[CanonicalizationResult],
) -> int:
    canonicalized_conflicts = sum(
        1 for result in canonicalization_results if result.conflict_fields
    )
    if canonicalized_conflicts:
        return canonicalized_conflicts

    conflict_events = 0
    for event in list_deal_change_events(db_path):
        raw_fields = event.get("changed_fields_json")
        if not raw_fields:
            continue
        changed_fields = json.loads(str(raw_fields))
        if any(field != "source_url" for field in changed_fields):
            conflict_events += 1
    return conflict_events

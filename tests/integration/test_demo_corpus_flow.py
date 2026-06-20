from pathlib import Path

from pdi.demo_corpus import persist_demo_snapshots
from pdi.dedupe import canonicalize_pending_candidates
from pdi.extractors import extract_and_persist_snapshot
from pdi.scoring import persist_banking_deal_score, score_banking_deal
from pdi.storage import (
    initialize_database,
    list_banking_deal_candidates,
    list_banking_deals,
    list_deal_change_events,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "examples" / "demo_banking"
DEMO_CONFIG = REPO_ROOT / "config" / "banking_sources.demo.yaml"


def run_demo_flow(db_path):
    initialize_database(db_path)
    snapshot_ids = persist_demo_snapshots(
        db_path,
        demo_dir=DEMO_DIR,
        source_config=DEMO_CONFIG,
        retrieved_at="2026-06-18T12:00:00+00:00",
    )
    candidate_ids = [
        extract_and_persist_snapshot(db_path, snapshot_id)
        for snapshot_id in snapshot_ids
    ]
    canonicalization_results = canonicalize_pending_candidates(db_path)
    scores = [
        persist_banking_deal_score(db_path, int(deal["id"]))
        for deal in list_banking_deals(db_path)
    ]
    return snapshot_ids, candidate_ids, canonicalization_results, scores


def test_demo_corpus_flows_through_extraction_dedupe_and_scoring(tmp_path):
    db_path = tmp_path / "pdi-demo.sqlite"

    snapshot_ids, candidate_ids, canonicalization_results, scores = run_demo_flow(db_path)

    candidates = list_banking_deal_candidates(db_path)
    deals = list_banking_deals(db_path)
    subcategories = {deal["subcategory"] for deal in deals}

    assert len(snapshot_ids) == 11
    assert len(candidate_ids) == 11
    assert len(candidates) == 11
    assert len([candidate for candidate in candidates if candidate["rejected"]]) == 1
    assert {
        "checking_bonus",
        "savings_bonus",
        "checking_savings_bundle",
        "brokerage_bonus",
        "cd_bonus",
    }.issubset(subcategories)
    assert any(result.action in {"matched", "updated"} for result in canonicalization_results)
    assert any(result.conflict_fields for result in canonicalization_results)
    assert len(scores) == len(deals)
    assert all(deal["estimated_net_value_cents"] is not None for deal in deals)


def test_demo_corpus_marks_duplicate_conflict_and_non_deal_cases(tmp_path):
    db_path = tmp_path / "pdi-demo.sqlite"
    run_demo_flow(db_path)

    candidates = list_banking_deal_candidates(db_path)
    deals = list_banking_deals(db_path)
    northstar_deals = [
        deal
        for deal in deals
        if deal["institution_name"] == "Northstar Demo Bank"
    ]
    rejected = [candidate for candidate in candidates if candidate["rejected"]]

    assert len(northstar_deals) == 1
    assert northstar_deals[0]["status"] == "needs_review"
    assert len(rejected) == 1
    assert rejected[0]["source_name"] == "Demo Manual User Pasted Banking Notes"
    assert "No explicit banking promotion terms found" in rejected[0]["rejection_reason"]

    events = list_deal_change_events(db_path, deal_id=int(northstar_deals[0]["id"]))
    assert any("direct_deposit_required" in event["changed_fields_json"] for event in events)


def test_demo_corpus_supports_low_value_expired_and_ambiguous_follow_on_cases(tmp_path):
    db_path = tmp_path / "pdi-demo.sqlite"
    run_demo_flow(db_path)

    deals = list_banking_deals(db_path)
    scores = {
        deal["institution_name"]: score_banking_deal(db_path, int(deal["id"]))
        for deal in deals
    }
    prairie = next(deal for deal in deals if deal["institution_name"] == "Prairie Example Bank")
    lakeside = next(deal for deal in deals if deal["institution_name"] == "Lakeside Sample Bank")

    assert scores["Sunset Demo Bank"].recommended_action == "expired"
    assert scores["Lakeside Sample Bank"].gross_bonus_value == 2500
    assert scores["Lakeside Sample Bank"].estimated_net_value < 2500
    assert prairie["bonus_amount_cents"] is None
    assert prairie["expires_at"] is None
    assert lakeside["bonus_amount_cents"] == 2500

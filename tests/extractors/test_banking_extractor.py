import json
from pathlib import Path

from pdi.extractors import extract_and_persist_snapshot, extract_banking_deal
from pdi.storage import (
    get_banking_deal_candidate,
    initialize_database,
    insert_raw_snapshot,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "extractors"


def load_fixture(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


def metadata(**overrides):
    values = {
        "raw_snapshot_id": 42,
        "source_name": "Extractor Fixture Source",
        "source_url": "manual://extractor-fixture",
        "retrieved_at": "2026-06-17T12:00:00+00:00",
    }
    values.update(overrides)
    return values


def assert_evidence_matches_source(raw_text, candidate):
    normalized = " ".join(raw_text.split())
    assert candidate.evidence_spans
    for span in candidate.evidence_spans:
        assert normalized[span.start : span.end] == span.text


def evidence_fields(candidate):
    return {span.field for span in candidate.evidence_spans}


def test_extracts_checking_bonus_with_direct_deposit_and_evidence():
    raw_text = load_fixture("checking_direct_deposit.txt")

    candidate = extract_banking_deal(raw_text, metadata())

    assert candidate.rejected is False
    assert candidate.institution_name == "Northstar Mock Bank"
    assert candidate.subcategory == "checking_bonus"
    assert candidate.title == "Northstar Mock Bank $300 Checking Bonus"
    assert candidate.bonus_amount_cents == 30000
    assert candidate.direct_deposit_required is True
    assert candidate.direct_deposit_minimum_cents == 100000
    assert candidate.balance_hold_days is None
    assert candidate.monthly_fee_cents == 1200
    assert candidate.expires_at == "2026-12-31"
    assert candidate.application_deadline == "2026-12-31"
    assert candidate.state_restrictions == ["CA", "OR"]
    assert candidate.new_customer_only is True
    assert candidate.household_limit == "One bonus per household"
    assert candidate.confidence_score >= 0.75
    assert "bonus_amount_cents" not in candidate.missing_fields
    assert "expires_at" not in candidate.missing_fields
    assert_evidence_matches_source(raw_text, candidate)
    assert {
        "bonus_amount_cents",
        "direct_deposit_required",
        "direct_deposit_minimum_cents",
        "monthly_fee_cents",
    }.issubset(evidence_fields(candidate))


def test_extracts_savings_bonus_with_minimum_balance_hold():
    raw_text = load_fixture("savings_balance_hold.txt")

    candidate = extract_banking_deal(raw_text, metadata())

    assert candidate.rejected is False
    assert candidate.institution_name == "Riverbend Sample Bank"
    assert candidate.subcategory == "savings_bonus"
    assert candidate.bonus_amount_cents == 50000
    assert candidate.minimum_deposit_amount_cents == 2500000
    assert candidate.minimum_balance_required_cents == 2500000
    assert candidate.balance_hold_days == 90
    assert candidate.direct_deposit_required is False
    assert candidate.monthly_fee_cents == 0
    assert candidate.expires_at == "2026-11-30"
    assert_evidence_matches_source(raw_text, candidate)
    assert {
        "bonus_amount_cents",
        "minimum_deposit_amount_cents",
        "minimum_balance_required_cents",
        "balance_hold_days",
        "direct_deposit_required",
    }.issubset(evidence_fields(candidate))


def test_extracts_brokerage_tiered_bonus_amounts():
    raw_text = load_fixture("brokerage_tiers.txt")

    candidate = extract_banking_deal(raw_text, metadata())

    assert candidate.rejected is False
    assert candidate.institution_name == "Harbor Demo Brokerage"
    assert candidate.subcategory == "brokerage_bonus"
    assert candidate.bonus_amount_cents == 75000
    assert candidate.minimum_deposit_amount_cents == 2500000
    assert candidate.balance_hold_days == 180
    assert candidate.expires_at == "2026-10-15"
    assert candidate.soft_pull_only is True
    assert candidate.tiered_bonus == [
        {
            "bonus_amount_cents": 10000,
            "minimum_deposit_amount_cents": 2500000,
        },
        {
            "bonus_amount_cents": 30000,
            "minimum_deposit_amount_cents": 10000000,
        },
        {
            "bonus_amount_cents": 75000,
            "minimum_deposit_amount_cents": 25000000,
        },
    ]
    assert_evidence_matches_source(raw_text, candidate)
    assert {
        "tiered_bonus",
        "bonus_amount_cents",
        "minimum_deposit_amount_cents",
        "balance_hold_days",
    }.issubset(evidence_fields(candidate))


def test_ambiguous_promo_keeps_missing_expiration_unknown():
    raw_text = load_fixture("ambiguous_missing_expiration.txt")

    candidate = extract_banking_deal(raw_text, metadata())

    assert candidate.rejected is False
    assert candidate.institution_name == "Prairie Example Bank"
    assert candidate.subcategory == "savings_bonus"
    assert candidate.bonus_amount_cents is None
    assert candidate.expires_at is None
    assert candidate.application_deadline is None
    assert candidate.minimum_deposit_amount_cents == 1000000
    assert candidate.balance_hold_days == 60
    assert "bonus_amount_cents" in candidate.missing_fields
    assert "expires_at" in candidate.missing_fields
    assert_evidence_matches_source(raw_text, candidate)


def test_non_deal_article_is_rejected_low_confidence():
    raw_text = load_fixture("non_deal_article.txt")

    candidate = extract_banking_deal(raw_text, metadata())

    assert candidate.rejected is True
    assert candidate.confidence_score < 0.35
    assert candidate.rejection_reason in {
        "No explicit banking promotion terms found.",
        "Low confidence extraction.",
    }
    assert candidate.bonus_amount_cents is None


def test_extract_and_persist_snapshot_links_candidate_to_raw_snapshot(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    raw_text = load_fixture("checking_direct_deposit.txt")
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://checking-fixture",
            "source_name": "Checking Fixture",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": raw_text,
            "collector_name": "fixture",
        },
    )

    candidate_id = extract_and_persist_snapshot(db_path, snapshot_id)
    row = get_banking_deal_candidate(db_path, candidate_id)

    assert row is not None
    assert row["raw_snapshot_id"] == snapshot_id
    assert row["source_name"] == "Checking Fixture"
    assert row["bonus_amount_cents"] == 30000
    assert row["direct_deposit_required"] == 1
    assert row["rejected"] == 0
    evidence = json.loads(row["evidence_spans_json"])
    missing_fields = json.loads(row["missing_fields_json"])
    assert any(span["field"] == "bonus_amount_cents" for span in evidence)
    assert "bonus_amount_cents" not in missing_fields

import json
from pathlib import Path

from pdi.extractors import extract_and_persist_snapshot, extract_banking_deal
from pdi.storage import (
    get_banking_deal_candidate,
    initialize_database,
    insert_raw_snapshot,
)


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "extractors"
    / "credit_cards"
)
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"


FIELD_MAP = {
    "issuer": "issuer_name",
    "card_name": "card_name",
    "product_family": "product_family",
    "customer_type": "customer_type",
    "card_network": "card_network",
    "offer_title": "title",
    "offer_currency": "offer_currency",
    "headline_bonus_amount": "headline_bonus_amount",
    "headline_bonus_value_cents": "headline_bonus_value_cents",
    "minimum_spend_cents": "minimum_spend_cents",
    "spend_window_days": "spend_window_days",
    "annual_fee_cents": "annual_fee_cents",
    "first_year_annual_fee_waived": "first_year_annual_fee_waived",
    "statement_credit_amount_cents": "statement_credit_amount_cents",
    "statement_credit_requirements": "statement_credit_requirements",
    "bonus_payout_timing": "bonus_payout_timing",
    "offer_expiration_date": "expires_at",
    "targeted": "targeted",
    "eligibility_restriction_notes": "eligibility_restriction_notes",
}


def manifest_entries():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["fixtures"]


def load_candidate(entry):
    text = (FIXTURE_ROOT / entry["file"]).read_text(encoding="utf-8")
    return extract_banking_deal(
        text,
        {
            "raw_snapshot_id": 42,
            "source_name": entry["id"],
            "source_url": entry["expected"]["source_url"],
            "retrieved_at": "2026-06-21T12:00:00+00:00",
        },
    )


def evidence_fields(candidate):
    return {span.field for span in candidate.evidence_spans}


def assert_evidence_matches_source(entry, candidate):
    text = " ".join((FIXTURE_ROOT / entry["file"]).read_text(encoding="utf-8").split())
    for span in candidate.evidence_spans:
        assert text[span.start : span.end] == span.text


def test_extracts_every_credit_card_fixture_against_manifest_expectations():
    for entry in manifest_entries():
        expected = entry["expected"]
        candidate = load_candidate(entry)

        assert candidate.category == "banking"
        assert candidate.subcategory == "credit_card_signup_bonus"
        assert candidate.rejected is (not expected["is_deal"])
        for expected_field, candidate_attr in FIELD_MAP.items():
            assert getattr(candidate, candidate_attr) == expected[expected_field], (
                entry["id"],
                expected_field,
            )
        assert candidate.source_url == expected["source_url"]
        assert candidate.point_mile_valuation_assumption_id is None
        assert expected["expected_missing_critical_fields"] == candidate.missing_fields
        assert set(expected["expected_evidence_fields"]).issubset(
            evidence_fields(candidate)
        )
        assert_evidence_matches_source(entry, candidate)


def test_credit_card_non_deal_page_is_rejected_with_unknown_offer_values():
    entry = next(
        item for item in manifest_entries() if item["id"] == "benefits_only_non_deal"
    )

    candidate = load_candidate(entry)

    assert candidate.rejected is True
    assert candidate.rejection_reason == "No explicit credit-card acquisition offer found."
    assert candidate.offer_currency == "unknown"
    assert candidate.headline_bonus_amount is None
    assert candidate.minimum_spend_cents is None
    assert candidate.spend_window_days is None


def test_credit_card_targeted_offer_is_flagged_for_review_without_advice():
    entry = next(item for item in manifest_entries() if item["id"] == "targeted_offer")

    candidate = load_candidate(entry)

    assert candidate.rejected is False
    assert candidate.targeted is True
    assert "Invitation code required." in candidate.eligibility_restriction_notes
    assert "Offer is not transferable." in candidate.eligibility_restriction_notes
    assert candidate.extraction_notes == [
        "Targeted or invitation-only language requires manual review."
    ]


def test_credit_card_unknown_values_remain_none():
    business = next(item for item in manifest_entries() if item["id"] == "business_card")
    statement_credit = next(
        item for item in manifest_entries() if item["id"] == "statement_credit_card"
    )
    miles = next(item for item in manifest_entries() if item["id"] == "miles_bonus_card")
    duplicate_roundup = next(
        item for item in manifest_entries() if item["id"] == "duplicate_offer_source_b"
    )
    expired = next(
        item for item in manifest_entries() if item["id"] == "expired_card_offer"
    )

    business_candidate = load_candidate(business)
    statement_candidate = load_candidate(statement_credit)
    miles_candidate = load_candidate(miles)
    duplicate_candidate = load_candidate(duplicate_roundup)
    expired_candidate = load_candidate(expired)

    assert business_candidate.bonus_payout_timing is None
    assert "bonus_payout_timing" in business_candidate.missing_fields
    assert statement_candidate.card_network is None
    assert "card_network" in statement_candidate.missing_fields
    assert miles_candidate.first_year_annual_fee_waived is None
    assert duplicate_candidate.customer_type == "unknown"
    assert expired_candidate.targeted is None


def test_credit_card_candidate_persists_structured_fields(tmp_path):
    entry = next(item for item in manifest_entries() if item["id"] == "mixed_bonus_card")
    text = (FIXTURE_ROOT / entry["file"]).read_text(encoding="utf-8")
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": entry["expected"]["source_url"],
            "source_name": entry["id"],
            "retrieved_at": "2026-06-21T12:00:00+00:00",
            "raw_text": text,
            "collector_name": "fixture",
        },
    )

    candidate_id = extract_and_persist_snapshot(db_path, snapshot_id)
    row = get_banking_deal_candidate(db_path, candidate_id)

    assert row["raw_snapshot_id"] == snapshot_id
    assert row["subcategory"] == "credit_card_signup_bonus"
    assert row["issuer_name"] == entry["expected"]["issuer"]
    assert row["card_name"] == entry["expected"]["card_name"]
    assert row["offer_currency"] == "mixed"
    assert json.loads(row["headline_bonus_amount_json"]) == {
        "points": 20000,
        "statement_credit_cents": 10000,
    }
    assert row["minimum_spend_cents"] == 250000
    assert row["spend_window_days"] == 120
    assert row["first_year_annual_fee_waived"] == 1
    assert row["targeted"] is None
    assert row["rejected"] == 0

import json

from pdi.dedupe import canonicalize_candidate, canonicalize_pending_candidates
from pdi.storage import (
    get_banking_deal,
    get_banking_deal_candidate,
    initialize_database,
    insert_banking_deal_candidate,
    insert_raw_snapshot,
    insert_source_record,
    list_banking_deal_source_links,
    list_banking_deals,
    list_deal_change_events,
    list_field_evidence_links,
)


def source_record(db_path, source_type="official_promo_page", name="Card Source"):
    return insert_source_record(
        db_path,
        {
            "source_name": name,
            "source_url": f"https://example.test/{name.lower().replace(' ', '-')}",
            "source_type": source_type,
            "collection_method": "manual_text",
            "enabled": True,
            "max_frequency": "manual_only",
            "compliance_notes": "Fictional credit-card source.",
        },
    )


def card_candidate(db_path, **overrides):
    source_id = overrides.pop("source_record_id", None)
    if source_id is None:
        source_id = source_record(db_path)
    source_url = overrides.get("source_url", "https://issuer.test/beacon/cash-forward")
    source_name = overrides.get("source_name", "Card Source")
    raw_snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_record_id": source_id,
            "source_url": source_url,
            "source_name": source_name,
            "retrieved_at": overrides.get("retrieved_at", "2026-06-21T12:00:00+00:00"),
            "raw_text": "Fictional credit-card acquisition offer text.",
            "collector_name": "fixture",
        },
    )
    values = {
        "raw_snapshot_id": raw_snapshot_id,
        "title": "Beacon Cash Forward Card $300 Cash Bonus",
        "institution_name": "Beacon Mock Bank",
        "issuer_name": "Beacon Mock Bank",
        "card_name": "Beacon Cash Forward Card",
        "product_family": "Cash Forward",
        "customer_type": "personal",
        "subcategory": "credit_card_signup_bonus",
        "bonus_amount_cents": 30000,
        "source_url": source_url,
        "source_name": source_name,
        "retrieved_at": "2026-06-21T12:00:00+00:00",
        "expires_at": "2026-12-15",
        "application_deadline": "2026-12-15",
        "offer_currency": "cash",
        "headline_bonus_amount": 300,
        "headline_bonus_value_cents": 30000,
        "minimum_spend_cents": 150000,
        "spend_window_days": 90,
        "annual_fee_cents": 0,
        "first_year_annual_fee_waived": False,
        "targeted": False,
        "eligibility_restriction_notes": [],
        "evidence_spans": [
            {
                "field": "headline_bonus_amount",
                "text": "$300",
                "start": 10,
                "end": 14,
            },
            {
                "field": "minimum_spend_cents",
                "text": "$1,500",
                "start": 30,
                "end": 36,
            },
            {
                "field": "annual_fee_cents",
                "text": "$0 annual fee",
                "start": 50,
                "end": 63,
            },
        ],
        "missing_fields": [],
        "confidence_score": 0.9,
        "source_confidence": 0.9,
        "rejected": False,
    }
    values.update(overrides)
    values["raw_snapshot_id"] = raw_snapshot_id
    return insert_banking_deal_candidate(db_path, values)


def credit_card_terms(deal):
    return json.loads(deal["terms"]["terms_json"])["credit_card"]


def changed_fields(events):
    names = set()
    for event in events:
        names.update(json.loads(event["changed_fields_json"]))
    return names


def test_duplicate_credit_card_candidates_merge_into_one_canonical_deal(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = card_candidate(db_path)
    second_id = card_candidate(db_path, retrieved_at="2026-06-22T12:00:00+00:00")

    first = canonicalize_candidate(db_path, first_id)
    second = canonicalize_candidate(db_path, second_id)

    assert first.action == "created"
    assert second.action == "matched"
    assert first.deal_id == second.deal_id
    assert len(list_banking_deals(db_path)) == 1
    assert len(list_banking_deal_source_links(db_path, deal_id=first.deal_id)) == 2
    evidence = list_field_evidence_links(db_path, deal_id=first.deal_id)
    by_field = {item["field"]: item for item in evidence}
    assert by_field["headline_bonus_amount"]["extracted_value"] == 300
    assert by_field["minimum_spend_cents"]["extracted_value"] == 150000
    assert (
        get_banking_deal_candidate(db_path, second_id)["canonicalization_status"]
        == "matched"
    )


def test_same_credit_card_offer_across_sources_links_to_one_deal(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    issuer_source = source_record(db_path, "official_promo_page", "Issuer Landing")
    roundup_source = source_record(db_path, "deal_blog", "Card Roundup")
    first_id = card_candidate(
        db_path,
        source_record_id=issuer_source,
        source_url="https://issuer.test/beacon/cash-forward",
        source_name="Issuer Landing",
    )
    second_id = card_candidate(
        db_path,
        source_record_id=roundup_source,
        source_url="https://roundup.test/beacon-cash-forward",
        source_name="Card Roundup",
        confidence_score=0.82,
    )

    results = canonicalize_pending_candidates(db_path)

    assert results[0].action == "created"
    assert results[1].action in {"matched", "updated"}
    assert results[0].deal_id == results[1].deal_id
    links = list_banking_deal_source_links(db_path, deal_id=results[0].deal_id)
    assert {link["source_name"] for link in links} == {
        "Issuer Landing",
        "Card Roundup",
    }
    assert {link["source_authority"] for link in links} == {
        "official",
        "secondary",
    }


def test_different_credit_card_creates_separate_canonical_deal(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = card_candidate(db_path)
    second_id = card_candidate(
        db_path,
        title="Beacon Travel Card 60,000 Point Offer",
        card_name="Beacon Travel Card",
        product_family="Travel",
        offer_currency="points",
        headline_bonus_amount=60000,
        headline_bonus_value_cents=None,
        bonus_amount_cents=None,
        source_url="https://issuer.test/beacon/travel",
    )

    first = canonicalize_candidate(db_path, first_id)
    second = canonicalize_candidate(db_path, second_id)

    assert first.action == "created"
    assert second.action == "created"
    assert first.deal_id != second.deal_id
    assert len(list_banking_deals(db_path)) == 2


def test_credit_card_missing_card_name_does_not_merge_by_headline_only(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = card_candidate(db_path)
    second_id = card_candidate(
        db_path,
        card_name=None,
        title="Beacon Mock Bank $300 Card Offer",
        source_url="https://roundup.test/unknown-beacon-card",
    )

    first = canonicalize_candidate(db_path, first_id)
    second = canonicalize_candidate(db_path, second_id)

    assert first.action == "created"
    assert second.action == "created"
    assert first.deal_id != second.deal_id
    assert len(list_banking_deals(db_path)) == 2


def test_conflicting_credit_card_minimum_spend_marks_review(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = card_candidate(db_path, confidence_score=0.8)
    second_id = card_candidate(
        db_path,
        minimum_spend_cents=200000,
        confidence_score=0.9,
        source_url="https://archive.test/beacon-cash-forward",
    )

    canonicalize_candidate(db_path, first_id)
    result = canonicalize_candidate(db_path, second_id)

    deal = get_banking_deal(db_path, result.deal_id)
    events = list_deal_change_events(db_path, deal_id=result.deal_id)
    assert deal["status"] == "needs_review"
    assert credit_card_terms(deal)["minimum_spend_cents"] == 200000
    assert "minimum_spend_cents" in result.conflict_fields
    assert "minimum_spend_cents" in changed_fields(events)


def test_conflicting_credit_card_annual_fee_marks_review(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = card_candidate(db_path, annual_fee_cents=0, confidence_score=0.8)
    second_id = card_candidate(
        db_path,
        annual_fee_cents=9500,
        first_year_annual_fee_waived=None,
        confidence_score=0.9,
    )

    canonicalize_candidate(db_path, first_id)
    result = canonicalize_candidate(db_path, second_id)

    deal = get_banking_deal(db_path, result.deal_id)
    assert deal["status"] == "needs_review"
    assert credit_card_terms(deal)["annual_fee_cents"] == 9500
    assert "annual_fee_cents" in result.conflict_fields


def test_conflicting_credit_card_targeted_status_marks_review(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = card_candidate(db_path, targeted=False, confidence_score=0.8)
    second_id = card_candidate(
        db_path,
        targeted=True,
        eligibility_restriction_notes=["Invitation code required."],
        confidence_score=0.9,
        source_url="manual://beacon-targeted-mailer",
    )

    canonicalize_candidate(db_path, first_id)
    result = canonicalize_candidate(db_path, second_id)

    deal = get_banking_deal(db_path, result.deal_id)
    assert deal["status"] == "needs_review"
    assert credit_card_terms(deal)["targeted"] is True
    assert "targeted" in result.conflict_fields
    assert "eligibility_restriction_notes" in result.changed_fields


def test_expired_credit_card_offer_canonicalizes_deterministically(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    candidate_id = card_candidate(
        db_path,
        title="Pioneer Miles Explorer Card 40,000 Mile Expired Offer",
        institution_name="Pioneer Demo Bank",
        issuer_name="Pioneer Demo Bank",
        card_name="Pioneer Miles Explorer Card",
        product_family="Miles Explorer",
        offer_currency="miles",
        headline_bonus_amount=40000,
        headline_bonus_value_cents=None,
        bonus_amount_cents=None,
        minimum_spend_cents=200000,
        annual_fee_cents=7900,
        expires_at="2025-05-31",
        application_deadline="2025-05-31",
        source_url="https://archive.test/pioneer-miles-explorer",
    )

    result = canonicalize_candidate(db_path, candidate_id)
    deal = get_banking_deal(db_path, result.deal_id)

    assert result.action == "created"
    assert deal["expires_at"] == "2025-05-31"
    assert credit_card_terms(deal)["offer_currency"] == "miles"
    assert credit_card_terms(deal)["headline_bonus_amount"] == 40000

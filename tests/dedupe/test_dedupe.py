import json
import sqlite3

from pdi.dedupe import (
    canonicalize_candidate,
    canonicalize_pending_candidates,
    generate_canonical_key,
)
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
)


def source_record(db_path, source_type="deal_blog", name="Fixture Source"):
    return insert_source_record(
        db_path,
        {
            "source_name": name,
            "source_url": f"https://example.test/{name.lower().replace(' ', '-')}",
            "source_type": source_type,
            "collection_method": "manual_text",
            "enabled": True,
            "max_frequency": "manual_only",
            "compliance_notes": "Fictional test source.",
        },
    )


def candidate(db_path, **overrides):
    source_id = overrides.pop("source_record_id", None)
    if source_id is None:
        source_id = source_record(db_path)
    raw_snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_record_id": source_id,
            "source_url": overrides.get("source_url", "https://deals.test/northstar"),
            "source_name": overrides.get("source_name", "Fixture Source"),
            "retrieved_at": overrides.get("retrieved_at", "2026-06-17T12:00:00+00:00"),
            "raw_text": "Fictional banking promotion text.",
            "collector_name": "fixture",
        },
    )
    values = {
        "raw_snapshot_id": raw_snapshot_id,
        "title": "Northstar Mock Bank $300 Everyday Checking Bonus",
        "institution_name": "Northstar Mock Bank",
        "subcategory": "checking_bonus",
        "bonus_amount_cents": 30000,
        "source_url": "https://deals.test/northstar/everyday-checking",
        "source_name": "Fixture Source",
        "retrieved_at": "2026-06-17T12:00:00+00:00",
        "expires_at": "2026-12-31",
        "application_deadline": "2026-12-31",
        "direct_deposit_required": True,
        "direct_deposit_minimum_cents": 100000,
        "minimum_deposit_amount_cents": None,
        "minimum_balance_required_cents": None,
        "monthly_fee_cents": 1200,
        "state_restrictions": ["CA", "OR"],
        "new_customer_only": True,
        "evidence_spans": [
            {
                "field": "bonus_amount_cents",
                "text": "$300",
                "start": 10,
                "end": 14,
            }
        ],
        "missing_fields": [],
        "confidence_score": 0.82,
        "rejected": False,
    }
    values.update(overrides)
    values["raw_snapshot_id"] = raw_snapshot_id
    return insert_banking_deal_candidate(db_path, values)


def test_generate_canonical_key_uses_more_than_title(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    candidate_id = candidate(db_path)
    row = get_banking_deal_candidate(db_path, candidate_id)

    key = generate_canonical_key(row)

    assert "northstar-mock" in key
    assert "checking-bonus" in key
    assert "bonus-30000" in key
    assert "2026-12-31" in key
    assert "deals-test-northstar-everyday-checking" in key


def test_exact_duplicate_candidates_merge_into_one_canonical_deal(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = candidate(db_path)
    second_id = candidate(db_path, retrieved_at="2026-06-18T12:00:00+00:00")

    first = canonicalize_candidate(db_path, first_id)
    second = canonicalize_candidate(db_path, second_id)

    assert first.action == "created"
    assert second.action == "matched"
    assert first.deal_id == second.deal_id
    assert len(list_banking_deals(db_path)) == 1
    assert len(list_banking_deal_source_links(db_path, deal_id=first.deal_id)) == 2
    assert (
        get_banking_deal_candidate(db_path, second_id)["canonicalization_status"]
        == "matched"
    )


def test_same_deal_from_two_sources_links_to_one_canonical_deal(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    blog_source_id = source_record(db_path, "deal_blog", "Deal Blog")
    rss_source_id = source_record(db_path, "rss_feed", "RSS Fixture")
    first_id = candidate(
        db_path,
        source_record_id=blog_source_id,
        source_url="https://blog.test/banking/northstar-everyday",
        source_name="Deal Blog",
    )
    second_id = candidate(
        db_path,
        source_record_id=rss_source_id,
        source_url="https://rss.test/items/northstar-everyday",
        source_name="RSS Fixture",
        confidence_score=0.8,
    )

    results = canonicalize_pending_candidates(db_path)

    assert [result.action for result in results] == ["created", "updated"]
    assert results[0].deal_id == results[1].deal_id
    links = list_banking_deal_source_links(db_path, deal_id=results[0].deal_id)
    assert {link["source_name"] for link in links} == {"Deal Blog", "RSS Fixture"}
    assert {link["source_authority"] for link in links} == {"secondary"}


def test_different_bonus_amount_creates_separate_deal_when_context_differs(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = candidate(db_path)
    second_id = candidate(
        db_path,
        title="Northstar Mock Bank $500 Premium Checking Bonus",
        bonus_amount_cents=50000,
        source_url="https://deals.test/northstar/premium-checking",
    )

    first = canonicalize_candidate(db_path, first_id)
    second = canonicalize_candidate(db_path, second_id)

    assert first.action == "created"
    assert second.action == "created"
    assert first.deal_id != second.deal_id
    assert len(list_banking_deals(db_path)) == 2


def test_expiration_update_creates_change_event(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = candidate(db_path, confidence_score=0.7)
    second_id = candidate(
        db_path,
        expires_at="2027-01-31",
        application_deadline="2027-01-31",
        confidence_score=0.9,
    )

    canonicalize_candidate(db_path, first_id)
    result = canonicalize_candidate(db_path, second_id)

    deal = get_banking_deal(db_path, result.deal_id)
    events = list_deal_change_events(db_path, deal_id=result.deal_id)
    changed = [json.loads(event["changed_fields_json"]) for event in events]
    assert result.action == "updated"
    assert deal["expires_at"] == "2027-01-31"
    assert any("expires_at" in event for event in changed)
    assert any("application_deadline" in event for event in changed)


def test_low_confidence_candidate_does_not_overwrite_high_confidence_data(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = candidate(db_path, confidence_score=0.9)
    second_id = candidate(db_path, bonus_amount_cents=50000, confidence_score=0.4)

    canonicalize_candidate(db_path, first_id)
    result = canonicalize_candidate(db_path, second_id)

    deal = get_banking_deal(db_path, result.deal_id)
    events = list_deal_change_events(db_path, deal_id=result.deal_id)
    assert deal["bonus_amount_cents"] == 30000
    assert "bonus_amount_cents" in result.conflict_fields
    assert any("bonus_amount_cents" in event["changed_fields_json"] for event in events)


def test_conflicting_important_fields_mark_deal_as_needs_review(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_id = candidate(db_path, confidence_score=0.7)
    second_id = candidate(
        db_path,
        source_url="https://rss.test/items/northstar-everyday",
        source_name="RSS Fixture",
        direct_deposit_required=False,
        confidence_score=0.9,
    )

    canonicalize_candidate(db_path, first_id)
    result = canonicalize_candidate(db_path, second_id)

    deal = get_banking_deal(db_path, result.deal_id)
    assert deal["status"] == "needs_review"
    assert deal["terms"]["direct_deposit_required"] == 0
    assert "direct_deposit_required" in result.conflict_fields
    with sqlite3.connect(db_path) as connection:
        status_events = connection.execute(
            "SELECT new_status FROM deal_status_events WHERE deal_id = ?",
            (result.deal_id,),
        ).fetchall()
    assert ("needs_review",) in status_events

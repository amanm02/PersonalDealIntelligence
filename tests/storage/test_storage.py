import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from importlib import resources
from pathlib import Path

import pytest

from pdi.storage import (
    acquire_banking_run_lock,
    get_banking_deal,
    get_banking_deal_candidate,
    get_banking_run,
    get_raw_snapshot,
    initialize_database,
    insert_banking_deal,
    insert_banking_deal_candidate,
    insert_banking_deal_source_link,
    insert_banking_run,
    insert_raw_snapshot,
    insert_source_record,
    insert_status_event,
    list_banking_deals,
    list_banking_deal_candidates,
    list_banking_deal_source_links,
    list_banking_runs,
    list_pending_banking_deal_candidates,
    list_field_evidence_links,
    list_missing_field_evidence,
    list_raw_snapshots,
    list_raw_snapshots_by_content_hash,
    load_seed_fixture,
    mark_banking_deal_candidate_canonicalized,
    release_banking_run_lock,
    update_banking_run,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "banking_deals.json"


def test_initializes_database_from_scratch(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "schema_migrations",
            "source_records",
            "raw_deal_snapshots",
            "banking_deals",
            "banking_deal_terms",
            "banking_deal_candidates",
            "banking_deal_source_links",
            "banking_field_evidence_links",
            "banking_runs",
            "banking_run_locks",
            "deal_status_events",
            "deal_change_events",
        }.issubset(table_names)
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0] == 8


def test_migrations_are_idempotent(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    initialize_database(db_path)
    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0] == 8


def test_raw_snapshot_content_hash_is_stable_and_content_derived(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    raw_text = "Mock Bank offers a fictional $300 checking bonus."

    first_id = insert_raw_snapshot(
        db_path,
        {
            "source_name": "Mock Hash Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": raw_text,
            "collector_name": "fixture",
        },
    )
    second_id = insert_raw_snapshot(
        db_path,
        {
            "source_name": "Mock Hash Source",
            "retrieved_at": "2026-06-17T12:05:00+00:00",
            "raw_text": raw_text,
            "collector_name": "fixture",
        },
    )
    changed_id = insert_raw_snapshot(
        db_path,
        {
            "source_name": "Mock Hash Source",
            "retrieved_at": "2026-06-17T12:10:00+00:00",
            "raw_text": raw_text + " Updated terms.",
            "collector_name": "fixture",
        },
    )

    expected_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    first = get_raw_snapshot(db_path, first_id)
    second = get_raw_snapshot(db_path, second_id)
    changed = get_raw_snapshot(db_path, changed_id)

    assert first["content_hash"] == expected_hash
    assert len(first["content_hash"]) == 64
    assert second["content_hash"] == first["content_hash"]
    assert changed["content_hash"] != first["content_hash"]


def test_raw_snapshot_metadata_round_trips_and_duplicate_hashes_are_queryable(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    source_id = insert_source_record(
        db_path,
        {
            "source_name": "Mock Metadata Source",
            "source_url": "manual://metadata",
            "source_type": "manual_url",
            "collection_method": "manual_text",
            "enabled": True,
            "max_frequency": "manual_only",
            "compliance_notes": "Fictional test source.",
        },
    )
    raw_text = "Mock Bank offers a fictional $300 checking bonus."
    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    first_id = insert_raw_snapshot(
        db_path,
        {
            "source_record_id": source_id,
            "source_url": "manual://metadata",
            "source_name": "Mock Metadata Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "content_hash": content_hash,
            "raw_text": raw_text,
            "raw_html_path": "/tmp/mock-metadata.html",
            "raw_payload_json": {"fixture_id": "metadata", "nested": {"b": 2}},
            "http_status": 200,
            "collector_name": "manual_text",
        },
    )
    second_id = insert_raw_snapshot(
        db_path,
        {
            "source_record_id": source_id,
            "source_url": "manual://metadata-copy",
            "source_name": "Mock Metadata Source Copy",
            "retrieved_at": "2026-06-17T12:05:00+00:00",
            "raw_text": raw_text,
            "raw_payload_json": {"fixture_id": "metadata-copy"},
            "collector_name": "manual_text",
        },
    )

    first = get_raw_snapshot(db_path, first_id)
    duplicates = list_raw_snapshots_by_content_hash(db_path, content_hash)
    snapshots = list_raw_snapshots(db_path)

    assert first["source_record_id"] == source_id
    assert first["source_url"] == "manual://metadata"
    assert first["source_name"] == "Mock Metadata Source"
    assert first["retrieved_at"] == "2026-06-17T12:00:00+00:00"
    assert first["raw_text"] == raw_text
    assert first["raw_html_path"] == "/tmp/mock-metadata.html"
    assert json.loads(first["raw_payload_json"]) == {
        "fixture_id": "metadata",
        "nested": {"b": 2},
    }
    assert first["http_status"] == 200
    assert first["collector_name"] == "manual_text"
    assert [snapshot["id"] for snapshot in duplicates] == [first_id, second_id]
    assert {snapshot["content_hash"] for snapshot in duplicates} == {content_hash}
    assert [snapshot["id"] for snapshot in snapshots] == [first_id, second_id]


def test_raw_snapshot_rejects_mismatched_supplied_content_hash(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)

    with pytest.raises(ValueError, match="content_hash must match raw_text"):
        insert_raw_snapshot(
            db_path,
            {
                "source_name": "Mock Hash Source",
                "retrieved_at": "2026-06-17T12:00:00+00:00",
                "content_hash": "0" * 64,
                "raw_text": "A different raw snapshot body.",
                "collector_name": "fixture",
            },
        )


def test_candidate_schema_is_hardened_on_fresh_database(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]: row
            for row in connection.execute(
                "PRAGMA table_info(banking_deal_candidates)"
            )
        }
        indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(banking_deal_candidates)"
            )
        }
        foreign_keys = [
            row
            for row in connection.execute(
                "PRAGMA foreign_key_list(banking_deal_candidates)"
            )
        ]

    assert "raw_snapshot_id" in columns
    assert columns["raw_snapshot_id"][3] == 1
    assert "evidence_spans_json" in columns
    assert "missing_fields_json" in columns
    assert "extraction_notes_json" in columns
    assert "raw_pattern_matches_json" in columns
    assert "canonical_deal_id" in columns
    assert "canonicalization_status" in columns
    assert "issuer_name" in columns
    assert "card_name" in columns
    assert "product_family" in columns
    assert "customer_type" in columns
    assert "card_network" in columns
    assert "offer_currency" in columns
    assert "headline_bonus_amount_json" in columns
    assert "headline_bonus_value_cents" in columns
    assert "minimum_spend_cents" in columns
    assert "spend_window_days" in columns
    assert "annual_fee_cents" in columns
    assert "first_year_annual_fee_waived" in columns
    assert "statement_credit_amount_cents" in columns
    assert "statement_credit_requirements" in columns
    assert "bonus_payout_timing" in columns
    assert "targeted" in columns
    assert "eligibility_restriction_notes_json" in columns
    assert "source_confidence" in columns
    assert "idx_banking_deal_candidates_raw_snapshot_id" in indexes
    assert "idx_banking_deal_candidates_rejected" in indexes
    assert "idx_banking_deal_candidates_canonicalization_status" in indexes
    assert "idx_banking_deal_candidates_card_name" in indexes
    assert "idx_banking_deal_candidates_offer_currency" in indexes
    assert any(
        row[2] == "raw_deal_snapshots"
        and row[3] == "raw_snapshot_id"
        and row[4] == "id"
        for row in foreign_keys
    )


def test_candidate_insert_retrieve_preserves_nulls_and_deterministic_json(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://candidate-json",
            "source_name": "Candidate JSON Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": "Mock Bank offers a $300 checking bonus.",
            "collector_name": "fixture",
        },
    )

    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Candidate JSON Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "state_restrictions": ["OR", "CA"],
            "evidence_spans": [
                {
                    "text": "$300",
                    "start": 19,
                    "field": "bonus_amount_cents",
                    "end": 23,
                }
            ],
            "missing_fields": ["direct_deposit_required", "expires_at"],
            "extraction_notes": ["ambiguous direct deposit requirement"],
            "tiered_bonus": [
                {
                    "minimum_deposit_amount_cents": 100000,
                    "bonus_amount_cents": 30000,
                }
            ],
            "raw_pattern_matches": {
                "minimum_deposit": ["$1,000"],
                "bonus_amount": ["$300"],
            },
            "confidence_score": 0.7,
        },
    )

    row = get_banking_deal_candidate(db_path, candidate_id)

    assert row["raw_snapshot_id"] == snapshot_id
    assert row["direct_deposit_required"] is None
    assert row["minimum_deposit_amount_cents"] is None
    assert row["expires_at"] is None
    assert row["state_restrictions_json"] == '["OR", "CA"]'
    assert row["evidence_spans_json"] == (
        '[{"end": 23, "field": "bonus_amount_cents", '
        '"start": 19, "text": "$300"}]'
    )
    assert row["missing_fields_json"] == (
        '["direct_deposit_required", "expires_at"]'
    )
    assert row["extraction_notes_json"] == (
        '["ambiguous direct deposit requirement"]'
    )
    assert row["tiered_bonus_json"] == (
        '[{"bonus_amount_cents": 30000, '
        '"minimum_deposit_amount_cents": 100000}]'
    )
    assert row["raw_pattern_matches_json"] == (
        '{"bonus_amount": ["$300"], "minimum_deposit": ["$1,000"]}'
    )


def test_credit_card_candidate_fields_round_trip_from_storage(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://card-candidate",
            "source_name": "Card Candidate Source",
            "retrieved_at": "2026-06-21T12:00:00+00:00",
            "raw_text": "Mock card issuer offers a fictional card bonus.",
            "collector_name": "fixture",
        },
    )

    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Example Card $200 Cash Bonus",
            "institution_name": "Example Issuer",
            "issuer_name": "Example Issuer",
            "card_name": "Example Cash Card",
            "product_family": "Cash",
            "customer_type": "personal",
            "card_network": "Visa",
            "subcategory": "credit_card_signup_bonus",
            "bonus_amount_cents": 20000,
            "offer_currency": "cash",
            "headline_bonus_amount": 200,
            "headline_bonus_value_cents": 20000,
            "minimum_spend_cents": 100000,
            "spend_window_days": 90,
            "annual_fee_cents": 0,
            "first_year_annual_fee_waived": False,
            "statement_credit_amount_cents": None,
            "statement_credit_requirements": None,
            "bonus_payout_timing": "8 weeks after qualifying spend",
            "targeted": True,
            "eligibility_restriction_notes": ["Invitation code required."],
            "source_confidence": 0.84,
            "source_name": "Card Candidate Source",
            "retrieved_at": "2026-06-21T12:00:00+00:00",
            "evidence_spans": [
                {
                    "field": "headline_bonus_amount",
                    "text": "$200",
                    "start": 0,
                    "end": 4,
                }
            ],
            "missing_fields": ["bonus_payout_timing"],
            "confidence_score": 0.84,
        },
    )

    row = get_banking_deal_candidate(db_path, candidate_id)

    assert row["issuer_name"] == "Example Issuer"
    assert row["card_name"] == "Example Cash Card"
    assert row["product_family"] == "Cash"
    assert row["customer_type"] == "personal"
    assert row["card_network"] == "Visa"
    assert row["offer_currency"] == "cash"
    assert row["headline_bonus_amount_json"] == "200"
    assert row["headline_bonus_value_cents"] == 20000
    assert row["minimum_spend_cents"] == 100000
    assert row["spend_window_days"] == 90
    assert row["annual_fee_cents"] == 0
    assert row["first_year_annual_fee_waived"] == 0
    assert row["bonus_payout_timing"] == "8 weeks after qualifying spend"
    assert row["targeted"] == 1
    assert row["eligibility_restriction_notes_json"] == (
        '["Invitation code required."]'
    )
    assert row["source_confidence"] == 0.84


def test_existing_candidate_rows_gain_credit_card_columns(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    _initialize_through_migration(db_path, "007")
    with sqlite3.connect(db_path) as connection:
        snapshot_id = connection.execute(
            """
            INSERT INTO raw_deal_snapshots (
              source_url,
              source_name,
              retrieved_at,
              content_hash,
              raw_text,
              collector_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "manual://legacy-credit-card",
                "Legacy Credit Card Source",
                "2026-06-21T12:00:00+00:00",
                hashlib.sha256(b"legacy credit card text").hexdigest(),
                "legacy credit card text",
                "fixture",
            ),
        ).lastrowid
        candidate_id = connection.execute(
            """
            INSERT INTO banking_deal_candidates (
              raw_snapshot_id,
              title,
              institution_name,
              category,
              subcategory,
              currency,
              source_name,
              retrieved_at,
              rejected
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                "Legacy Card Candidate",
                "Legacy Issuer",
                "banking",
                "credit_card_signup_bonus",
                "USD",
                "Legacy Credit Card Source",
                "2026-06-21T12:00:00+00:00",
                0,
            ),
        ).lastrowid
        connection.commit()

    initialize_database(db_path)
    row = get_banking_deal_candidate(db_path, candidate_id)

    assert row["subcategory"] == "credit_card_signup_bonus"
    assert row["issuer_name"] is None
    assert row["card_name"] is None
    assert row["offer_currency"] is None


def test_candidate_lifecycle_filters_rejected_and_canonicalization_status(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://candidate-filter",
            "source_name": "Candidate Filter Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": "Mock Bank offers a $300 checking bonus.",
            "collector_name": "fixture",
        },
    )
    kept_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Candidate Filter Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.8,
        },
    )
    rejected_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": None,
            "institution_name": None,
            "subcategory": None,
            "source_name": "Candidate Filter Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.1,
            "rejected": True,
            "rejection_reason": "Low confidence extraction.",
        },
    )
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "candidate-filter",
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Candidate Filter Source",
            "raw_snapshot_id": snapshot_id,
        },
    )

    mark_banking_deal_candidate_canonicalized(
        db_path,
        kept_id,
        deal_id=deal_id,
        status="created",
    )

    rejected = list_banking_deal_candidates(db_path, rejected=True)
    created = list_banking_deal_candidates(
        db_path,
        rejected=False,
        canonicalization_status="created",
    )
    pending = list_pending_banking_deal_candidates(db_path)

    assert [candidate["id"] for candidate in rejected] == [rejected_id]
    assert [candidate["id"] for candidate in created] == [kept_id]
    assert pending == []


def test_existing_candidate_rows_migrate_cleanly_from_candidate_migration(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    _initialize_through_migration(db_path, "002")
    with sqlite3.connect(db_path) as connection:
        snapshot_id = connection.execute(
            """
            INSERT INTO raw_deal_snapshots (
              source_url,
              source_name,
              retrieved_at,
              content_hash,
              raw_text,
              collector_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "manual://legacy-candidate",
                "Legacy Candidate Source",
                "2026-06-17T12:00:00+00:00",
                hashlib.sha256(b"legacy candidate text").hexdigest(),
                "legacy candidate text",
                "fixture",
            ),
        ).lastrowid
        candidate_id = connection.execute(
            """
            INSERT INTO banking_deal_candidates (
              raw_snapshot_id,
              title,
              institution_name,
              category,
              subcategory,
              bonus_amount_cents,
              currency,
              source_name,
              retrieved_at,
              evidence_spans_json,
              missing_fields_json,
              raw_pattern_matches_json,
              confidence_score,
              rejected
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                "Legacy Candidate Bank Bonus",
                "Legacy Candidate Bank",
                "banking",
                "checking_bonus",
                30000,
                "USD",
                "Legacy Candidate Source",
                "2026-06-17T12:00:00+00:00",
                "[]",
                '["expires_at"]',
                '{"bonus_amount": ["$300"]}',
                0.8,
                0,
            ),
        ).lastrowid
        connection.commit()

    initialize_database(db_path)
    pending = list_pending_banking_deal_candidates(db_path)
    mark_banking_deal_candidate_canonicalized(
        db_path,
        candidate_id,
        deal_id=None,
        status="skipped",
    )
    row = get_banking_deal_candidate(db_path, candidate_id)

    assert [candidate["id"] for candidate in pending] == [candidate_id]
    assert row["canonicalization_status"] == "skipped"
    assert row["canonicalized_at"] is not None


def test_candidate_raw_snapshot_foreign_key_is_enforced(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)

    with pytest.raises(sqlite3.IntegrityError):
        insert_banking_deal_candidate(
            db_path,
            {
                "raw_snapshot_id": 999,
                "title": "Missing Snapshot Candidate",
                "institution_name": "Missing Snapshot Bank",
                "subcategory": "checking_bonus",
                "source_name": "Missing Snapshot Source",
            },
        )


def test_source_link_schema_is_hardened_on_fresh_database(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]: row
            for row in connection.execute(
                "PRAGMA table_info(banking_deal_source_links)"
            )
        }
        indexes = [
            row
            for row in connection.execute(
                "PRAGMA index_list(banking_deal_source_links)"
            )
        ]
        foreign_keys = [
            row
            for row in connection.execute(
                "PRAGMA foreign_key_list(banking_deal_source_links)"
            )
        ]

    assert columns["deal_id"][3] == 1
    assert columns["candidate_id"][3] == 1
    assert columns["raw_snapshot_id"][3] == 1
    assert columns["source_name"][3] == 1
    assert columns["source_authority"][4] == "'unknown'"
    assert columns["link_type"][3] == 1
    assert columns["link_type"][4] == "'candidate_source'"
    assert "trust_tier" in columns
    assert "official_source" in columns
    assert "notes" in columns
    assert "evidence_json" in columns
    assert any(row[2] for row in indexes)
    assert {
        (row[2], row[3], row[4])
        for row in foreign_keys
        if row[2]
    }.issuperset(
        {
            ("banking_deals", "deal_id", "id"),
            ("banking_deal_candidates", "candidate_id", "id"),
            ("raw_deal_snapshots", "raw_snapshot_id", "id"),
        }
    )


def test_source_link_insert_list_and_duplicate_behavior_is_deterministic(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://source-link",
            "source_name": "Source Link Fixture",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": "Mock Bank offers a $300 checking bonus.",
            "collector_name": "fixture",
        },
    )
    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Source Link Fixture",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.8,
        },
    )
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "source-link-fixture",
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Source Link Fixture",
            "raw_snapshot_id": snapshot_id,
        },
    )

    first_link_id = insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Source Link Fixture",
            "source_url": "manual://source-link",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.8,
            "evidence": [
                {
                    "text": "$300",
                    "start": 19,
                    "field": "bonus_amount_cents",
                    "end": 23,
                }
            ],
        },
    )
    duplicate_link_id = insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Duplicate Ignored Source",
            "source_authority": "official",
            "link_type": "candidate_source",
            "trust_tier": "official",
            "official_source": True,
            "retrieved_at": "2026-06-17T13:00:00+00:00",
            "notes": "Duplicate metadata must not overwrite the first link.",
        },
    )

    by_deal = list_banking_deal_source_links(db_path, deal_id=deal_id)
    by_candidate = list_banking_deal_source_links(
        db_path,
        candidate_id=candidate_id,
    )

    assert duplicate_link_id == first_link_id
    assert [link["id"] for link in by_deal] == [first_link_id]
    assert [link["id"] for link in by_candidate] == [first_link_id]
    assert by_deal[0]["source_name"] == "Source Link Fixture"
    assert by_deal[0]["source_authority"] == "unknown"
    assert by_deal[0]["link_type"] == "candidate_source"
    assert by_deal[0]["trust_tier"] is None
    assert by_deal[0]["official_source"] is None
    assert by_deal[0]["notes"] is None
    assert by_deal[0]["evidence_json"] == (
        '[{"end": 23, "field": "bonus_amount_cents", '
        '"start": 19, "text": "$300"}]'
    )


def test_source_link_explicit_metadata_is_persisted(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://source-link-metadata",
            "source_name": "Source Link Metadata Fixture",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": "Mock Bank offers a $300 checking bonus.",
            "collector_name": "fixture",
        },
    )
    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Source Link Metadata Fixture",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.8,
        },
    )
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "source-link-metadata-fixture",
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Source Link Metadata Fixture",
            "raw_snapshot_id": snapshot_id,
        },
    )

    link_id = insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Source Link Metadata Fixture",
            "source_authority": "official",
            "link_type": "candidate_source",
            "trust_tier": "official",
            "official_source": True,
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "notes": "Reviewed official landing page.",
        },
    )

    link = list_banking_deal_source_links(db_path, candidate_id=candidate_id)[0]

    assert link["id"] == link_id
    assert link["source_authority"] == "official"
    assert link["link_type"] == "candidate_source"
    assert link["trust_tier"] == "official"
    assert link["official_source"] == 1
    assert link["notes"] == "Reviewed official landing page."


def test_existing_candidate_rows_can_link_after_source_link_migration(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    _initialize_through_migration(db_path, "002")
    with sqlite3.connect(db_path) as connection:
        snapshot_id = connection.execute(
            """
            INSERT INTO raw_deal_snapshots (
              source_url,
              source_name,
              retrieved_at,
              content_hash,
              raw_text,
              collector_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "manual://legacy-link",
                "Legacy Link Source",
                "2026-06-17T12:00:00+00:00",
                hashlib.sha256(b"legacy source link text").hexdigest(),
                "legacy source link text",
                "fixture",
            ),
        ).lastrowid
        candidate_id = connection.execute(
            """
            INSERT INTO banking_deal_candidates (
              raw_snapshot_id,
              title,
              institution_name,
              category,
              subcategory,
              bonus_amount_cents,
              currency,
              source_name,
              retrieved_at,
              evidence_spans_json,
              missing_fields_json,
              confidence_score,
              rejected
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                "Legacy Link Bank Bonus",
                "Legacy Link Bank",
                "banking",
                "checking_bonus",
                30000,
                "USD",
                "Legacy Link Source",
                "2026-06-17T12:00:00+00:00",
                "[]",
                "[]",
                0.8,
                0,
            ),
        ).lastrowid
        deal_id = connection.execute(
            """
            INSERT INTO banking_deals (
              canonical_key,
              title,
              institution_name,
              subcategory,
              bonus_amount_cents,
              discovered_at,
              last_seen_at,
              raw_snapshot_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-link-checking",
                "Legacy Link Bank Bonus",
                "Legacy Link Bank",
                "checking_bonus",
                30000,
                "2026-06-17T12:00:00+00:00",
                "2026-06-17T12:00:00+00:00",
                snapshot_id,
            ),
        ).lastrowid
        connection.commit()

    initialize_database(db_path)
    link_id = insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Legacy Link Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
        },
    )

    links = list_banking_deal_source_links(db_path, candidate_id=candidate_id)

    assert [link["id"] for link in links] == [link_id]
    assert links[0]["source_authority"] == "unknown"
    assert links[0]["link_type"] == "candidate_source"
    assert links[0]["trust_tier"] is None
    assert links[0]["official_source"] is None
    assert links[0]["notes"] is None


def test_existing_source_link_rows_migrate_with_default_metadata(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    _initialize_through_migration(db_path, "006")
    with sqlite3.connect(db_path) as connection:
        snapshot_id = connection.execute(
            """
            INSERT INTO raw_deal_snapshots (
              source_url,
              source_name,
              retrieved_at,
              content_hash,
              raw_text,
              collector_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "manual://legacy-source-link-row",
                "Legacy Source Link Row",
                "2026-06-17T12:00:00+00:00",
                hashlib.sha256(b"legacy source link row text").hexdigest(),
                "legacy source link row text",
                "fixture",
            ),
        ).lastrowid
        candidate_id = connection.execute(
            """
            INSERT INTO banking_deal_candidates (
              raw_snapshot_id,
              title,
              institution_name,
              category,
              subcategory,
              bonus_amount_cents,
              currency,
              source_name,
              retrieved_at,
              evidence_spans_json,
              missing_fields_json,
              confidence_score,
              rejected
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                "Legacy Source Link Bank Bonus",
                "Legacy Source Link Bank",
                "banking",
                "checking_bonus",
                30000,
                "USD",
                "Legacy Source Link Row",
                "2026-06-17T12:00:00+00:00",
                "[]",
                "[]",
                0.8,
                0,
            ),
        ).lastrowid
        deal_id = connection.execute(
            """
            INSERT INTO banking_deals (
              canonical_key,
              title,
              institution_name,
              subcategory,
              bonus_amount_cents,
              discovered_at,
              last_seen_at,
              raw_snapshot_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-source-link-row",
                "Legacy Source Link Bank Bonus",
                "Legacy Source Link Bank",
                "checking_bonus",
                30000,
                "2026-06-17T12:00:00+00:00",
                "2026-06-17T12:00:00+00:00",
                snapshot_id,
            ),
        ).lastrowid
        source_link_id = connection.execute(
            """
            INSERT INTO banking_deal_source_links (
              deal_id,
              candidate_id,
              raw_snapshot_id,
              source_name,
              source_url,
              source_authority,
              retrieved_at,
              confidence_score,
              evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deal_id,
                candidate_id,
                snapshot_id,
                "Legacy Source Link Row",
                "manual://legacy-source-link-row",
                "unknown",
                "2026-06-17T12:00:00+00:00",
                0.8,
                "[]",
            ),
        ).lastrowid
        connection.commit()

    initialize_database(db_path)
    duplicate_link_id = insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Duplicate Legacy Source Link Row",
            "source_authority": "official",
            "link_type": "candidate_source",
            "trust_tier": "official",
            "official_source": True,
            "notes": "Duplicate metadata must not overwrite the legacy row.",
        },
    )

    by_deal = list_banking_deal_source_links(db_path, deal_id=deal_id)
    by_candidate = list_banking_deal_source_links(
        db_path,
        candidate_id=candidate_id,
    )

    assert duplicate_link_id == source_link_id
    assert [link["id"] for link in by_deal] == [source_link_id]
    assert [link["id"] for link in by_candidate] == [source_link_id]
    assert by_deal[0]["source_name"] == "Legacy Source Link Row"
    assert by_deal[0]["source_authority"] == "unknown"
    assert by_deal[0]["link_type"] == "candidate_source"
    assert by_deal[0]["trust_tier"] is None
    assert by_deal[0]["official_source"] is None
    assert by_deal[0]["notes"] is None


def test_source_link_foreign_keys_are_enforced(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://source-link-fk",
            "source_name": "Source Link FK Fixture",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": "Mock Bank offers a $300 checking bonus.",
            "collector_name": "fixture",
        },
    )
    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Source Link FK Fixture",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.8,
        },
    )
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "source-link-fk-fixture",
            "title": "Mock Bank $300 Checking Bonus",
            "institution_name": "Mock Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Source Link FK Fixture",
            "raw_snapshot_id": snapshot_id,
        },
    )

    with pytest.raises(sqlite3.IntegrityError):
        insert_banking_deal_source_link(
            db_path,
            {
                "deal_id": 999,
                "candidate_id": candidate_id,
                "raw_snapshot_id": snapshot_id,
                "source_name": "Source Link FK Fixture",
            },
        )
    with pytest.raises(sqlite3.IntegrityError):
        insert_banking_deal_source_link(
            db_path,
            {
                "deal_id": deal_id,
                "candidate_id": 999,
                "raw_snapshot_id": snapshot_id,
                "source_name": "Source Link FK Fixture",
            },
        )
    with pytest.raises(sqlite3.IntegrityError):
        insert_banking_deal_source_link(
            db_path,
            {
                "deal_id": deal_id,
                "candidate_id": candidate_id,
                "raw_snapshot_id": 999,
                "source_name": "Source Link FK Fixture",
            },
        )


def test_field_evidence_links_are_queryable_from_source_links(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://evidence",
            "source_name": "Mock Evidence Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": "Mock Bank offers a $300 checking bonus.",
            "collector_name": "fixture",
        },
    )
    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Mock Evidence Bank $300 Checking Bonus",
            "institution_name": "Mock Evidence Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "source_name": "Mock Evidence Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "evidence_spans": [
                {"field": "bonus_amount_cents", "text": "$300", "start": 19, "end": 23}
            ],
            "missing_fields": [],
            "confidence_score": 0.8,
        },
    )
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "mock-evidence-checking",
            "title": "Mock Evidence Bank $300 Checking Bonus",
            "institution_name": "Mock Evidence Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "discovered_at": "2026-06-17T12:00:00+00:00",
            "last_seen_at": "2026-06-17T12:00:00+00:00",
            "raw_snapshot_id": snapshot_id,
        },
    )
    insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Mock Evidence Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.8,
            "evidence": [
                {
                    "field": "bonus_amount_cents",
                    "text": "$300",
                    "start": 19,
                    "end": 23,
                    "extracted_value": 30000,
                    "extraction_method": "fixture_parser",
                    "extraction_version": "test",
                }
            ],
        },
    )

    evidence = list_field_evidence_links(
        db_path,
        deal_id=deal_id,
        field_name="bonus_amount_cents",
    )

    assert len(evidence) == 1
    assert evidence[0]["deal_id"] == deal_id
    assert evidence[0]["candidate_id"] == candidate_id
    assert evidence[0]["raw_snapshot_id"] == snapshot_id
    assert evidence[0]["field"] == "bonus_amount_cents"
    assert evidence[0]["extracted_value"] == 30000
    assert evidence[0]["evidence_text"] == "$300"
    assert evidence[0]["content_hash"]
    assert evidence[0]["confidence_score"] == 0.8
    assert evidence[0]["extraction_method"] == "fixture_parser"
    assert evidence[0]["created_at"]


def test_missing_field_evidence_reports_populated_fields_without_links(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://missing-evidence",
            "source_name": "Mock Missing Evidence Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": "Mock Bank offers a checking bonus.",
            "collector_name": "fixture",
        },
    )
    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Mock Missing Evidence Bank Bonus",
            "institution_name": "Mock Missing Evidence Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "direct_deposit_required": True,
            "source_name": "Mock Missing Evidence Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "evidence_spans": [
                {"field": "bonus_amount_cents", "text": "$300", "start": 17, "end": 21}
            ],
            "missing_fields": [],
            "confidence_score": 0.8,
        },
    )
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "mock-missing-evidence-checking",
            "title": "Mock Missing Evidence Bank Bonus",
            "institution_name": "Mock Missing Evidence Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "discovered_at": "2026-06-17T12:00:00+00:00",
            "last_seen_at": "2026-06-17T12:00:00+00:00",
            "raw_snapshot_id": snapshot_id,
            "terms": {"direct_deposit_required": True},
        },
    )
    insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Mock Missing Evidence Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.8,
            "evidence": [
                {
                    "field": "bonus_amount_cents",
                    "text": "$300",
                    "start": 17,
                    "end": 21,
                    "extracted_value": 30000,
                }
            ],
        },
    )

    missing = list_missing_field_evidence(
        db_path,
        deal_id,
        field_names=("bonus_amount_cents", "direct_deposit_required"),
    )

    assert missing == [
        {
            "deal_id": deal_id,
            "field": "direct_deposit_required",
            "value": 1,
            "reason": "value_without_field_evidence",
        }
    ]


def test_field_evidence_links_backfill_existing_source_link_json(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    _initialize_through_migration(db_path, "005")
    with sqlite3.connect(db_path) as connection:
        snapshot_id = connection.execute(
            """
            INSERT INTO raw_deal_snapshots (
              source_url,
              source_name,
              retrieved_at,
              content_hash,
              raw_text,
              collector_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "manual://legacy-evidence",
                "Legacy Evidence Source",
                "2026-06-17T12:00:00+00:00",
                hashlib.sha256(b"legacy evidence text").hexdigest(),
                "legacy evidence text",
                "fixture",
            ),
        ).lastrowid
        candidate_id = connection.execute(
            """
            INSERT INTO banking_deal_candidates (
              raw_snapshot_id,
              title,
              institution_name,
              category,
              subcategory,
              bonus_amount_cents,
              currency,
              source_name,
              retrieved_at,
              evidence_spans_json,
              missing_fields_json,
              confidence_score,
              rejected
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                "Legacy Evidence Bank Bonus",
                "Legacy Evidence Bank",
                "banking",
                "checking_bonus",
                30000,
                "USD",
                "Legacy Evidence Source",
                "2026-06-17T12:00:00+00:00",
                "[]",
                "[]",
                0.8,
                0,
            ),
        ).lastrowid
        deal_id = connection.execute(
            """
            INSERT INTO banking_deals (
              canonical_key,
              title,
              institution_name,
              subcategory,
              bonus_amount_cents,
              discovered_at,
              last_seen_at,
              raw_snapshot_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-evidence-checking",
                "Legacy Evidence Bank Bonus",
                "Legacy Evidence Bank",
                "checking_bonus",
                30000,
                "2026-06-17T12:00:00+00:00",
                "2026-06-17T12:00:00+00:00",
                snapshot_id,
            ),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO banking_deal_source_links (
              deal_id,
              candidate_id,
              raw_snapshot_id,
              source_name,
              retrieved_at,
              confidence_score,
              evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deal_id,
                candidate_id,
                snapshot_id,
                "Legacy Evidence Source",
                "2026-06-17T12:00:00+00:00",
                0.8,
                json.dumps(
                    [
                        {
                            "field": "bonus_amount_cents",
                            "text": "$300",
                            "start": 0,
                            "end": 4,
                            "extracted_value": 30000,
                        },
                        {
                            "field": "tiered_bonus",
                            "text": "$300 for $25,000",
                            "start": 0,
                            "end": 16,
                        },
                    ],
                    sort_keys=True,
                ),
            ),
        )
        connection.commit()

    initialize_database(db_path)

    evidence = list_field_evidence_links(db_path, deal_id=deal_id)
    assert [item["field"] for item in evidence] == ["bonus_amount_cents"]
    assert evidence[0]["extracted_value"] == 30000
    assert evidence[0]["evidence_text"] == "$300"
    assert evidence[0]["raw_snapshot_id"] == snapshot_id
    assert evidence[0]["candidate_id"] == candidate_id


def test_insert_and_query_partial_deal_with_raw_snapshot_link(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)

    source_id = insert_source_record(
        db_path,
        {
            "source_name": "Mock Partial Source",
            "source_url": "manual://partial",
            "source_type": "manual_url",
            "collection_method": "manual_text",
            "enabled": True,
            "max_frequency": "manual_only",
            "compliance_notes": "Fictional test source.",
        },
    )
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_record_id": source_id,
            "source_url": "manual://partial",
            "source_name": "Mock Partial Source",
            "retrieved_at": "2026-06-17T13:00:00+00:00",
            "raw_text": "A fictional savings bonus with missing requirements.",
            "collector_name": "fixture",
        },
    )
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "partial-savings-bonus",
            "title": "Partial Savings Bonus",
            "institution_name": "Mock Partial Bank",
            "subcategory": "savings_bonus",
            "bonus_amount_cents": None,
            "estimated_net_value_cents": None,
            "source_url": "manual://partial",
            "source_name": "Mock Partial Source",
            "discovered_at": "2026-06-17T13:00:00+00:00",
            "last_seen_at": "2026-06-17T13:00:00+00:00",
            "status": "needs_review",
            "confidence_score": 0.4,
            "raw_snapshot_id": snapshot_id,
            "terms": {
                "minimum_deposit_amount_cents": None,
                "direct_deposit_required": None,
                "direct_deposit_minimum_cents": None,
                "terms_json": {"missing_fields": ["bonus_amount"]},
            },
        },
    )

    deal = get_banking_deal(db_path, deal_id)

    assert deal is not None
    assert deal["raw_snapshot_id"] == snapshot_id
    assert deal["bonus_amount_cents"] is None
    assert deal["status"] == "needs_review"
    assert deal["terms"]["direct_deposit_required"] is None
    assert deal["terms"]["terms_json"] == '{"missing_fields": ["bonus_amount"]}'
    assert list_banking_deals(db_path, status="needs_review")[0]["id"] == deal_id


def test_status_event_updates_deal_status(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://status",
            "source_name": "Mock Status Source",
            "retrieved_at": "2026-06-17T13:05:00+00:00",
            "raw_text": "A fictional checking bonus.",
            "collector_name": "fixture",
        },
    )
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "status-checking-bonus",
            "title": "Status Checking Bonus",
            "institution_name": "Mock Status Bank",
            "subcategory": "checking_bonus",
            "source_url": "manual://status",
            "source_name": "Mock Status Source",
            "discovered_at": "2026-06-17T13:05:00+00:00",
            "last_seen_at": "2026-06-17T13:05:00+00:00",
            "status": "new",
            "raw_snapshot_id": snapshot_id,
        },
    )

    event_id = insert_status_event(
        db_path,
        deal_id,
        "watching",
        note="Fixture status transition.",
    )

    assert event_id > 0
    assert get_banking_deal(db_path, deal_id)["status"] == "watching"
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM deal_status_events WHERE deal_id = ?",
            (deal_id,),
        ).fetchone()[0] == 2


def test_in_progress_status_is_supported(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = insert_banking_deal(
        db_path,
        {
            "canonical_key": "in-progress-checking-bonus",
            "title": "In Progress Checking Bonus",
            "institution_name": "Mock Progress Bank",
            "subcategory": "checking_bonus",
            "discovered_at": "2026-06-17T13:10:00+00:00",
            "last_seen_at": "2026-06-17T13:10:00+00:00",
            "status": "new",
        },
    )

    insert_status_event(
        db_path,
        deal_id,
        "in_progress",
        note="Reviewing official page.",
    )

    assert get_banking_deal(db_path, deal_id)["status"] == "in_progress"


def test_review_status_migration_preserves_applied_rows(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    _initialize_through_migration(db_path, "003")
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO banking_deals (
              canonical_key,
              title,
              institution_name,
              subcategory,
              discovered_at,
              last_seen_at,
              status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "applied-compatibility",
                "Applied Compatibility Bonus",
                "Mock Compatibility Bank",
                "checking_bonus",
                "2026-06-17T13:10:00+00:00",
                "2026-06-17T13:10:00+00:00",
                "applied",
            ),
        )
        connection.commit()

    initialize_database(db_path)
    deal = list_banking_deals(db_path, status="applied")[0]
    insert_status_event(db_path, deal["id"], "in_progress")

    assert deal["status"] == "applied"
    assert get_banking_deal(db_path, deal["id"])["status"] == "in_progress"


def test_seed_fixture_loads_three_mock_deals(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)

    loaded_count = load_seed_fixture(db_path, FIXTURE_PATH)

    assert loaded_count == 3
    deals = list_banking_deals(db_path)
    assert len(deals) == 3
    assert {deal["subcategory"] for deal in deals} == {
        "checking_bonus",
        "savings_bonus",
        "brokerage_bonus",
    }


def test_banking_run_history_records_counts_and_metadata(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)

    run_id = insert_banking_run(
        db_path,
        dry_run=True,
        metadata={"workflow": "fixture"},
    )
    update_banking_run(
        db_path,
        run_id,
        status="succeeded",
        counts={
            "sources": 2,
            "raw_snapshots": 2,
            "candidates": 2,
            "canonical_deals": 1,
            "conflicts": 1,
        },
        metadata={"workflow": "fixture", "digest_written": False},
    )

    run = get_banking_run(db_path, run_id)
    recent = list_banking_runs(db_path)

    assert run["status"] == "succeeded"
    assert run["dry_run"] == 1
    assert run["source_count"] == 2
    assert run["raw_snapshot_count"] == 2
    assert run["candidate_count"] == 2
    assert run["canonical_deal_count"] == 1
    assert run["conflict_count"] == 1
    assert run["metadata_json"] == '{"digest_written": false, "workflow": "fixture"}'
    assert recent[0]["id"] == run_id


def test_banking_run_lock_blocks_overlap_and_releases_owner(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    first_run = insert_banking_run(db_path, dry_run=True)
    second_run = insert_banking_run(db_path, dry_run=True)

    assert acquire_banking_run_lock(db_path, first_run) is True
    assert acquire_banking_run_lock(db_path, second_run) is False

    release_banking_run_lock(db_path, run_id=second_run)
    assert acquire_banking_run_lock(db_path, second_run) is False

    release_banking_run_lock(db_path, run_id=first_run)
    assert acquire_banking_run_lock(db_path, second_run) is True


def test_cli_initializes_and_loads_fixture_without_network(tmp_path):
    db_path = tmp_path / "pdi-cli.sqlite"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdi.storage",
            "init",
            "--db",
            str(db_path),
            "--seed-fixture",
            str(FIXTURE_PATH),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "seeded 3 mock deals" in result.stdout
    assert len(list_banking_deals(db_path)) == 3


def test_invalid_subcategory_fails_closed(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)

    with pytest.raises(sqlite3.IntegrityError):
        insert_banking_deal(
            db_path,
            {
                "canonical_key": "bad-category",
                "title": "Bad Category",
                "institution_name": "Mock Bank",
                "subcategory": "travel_deal",
                "discovered_at": "2026-06-17T13:10:00+00:00",
                "last_seen_at": "2026-06-17T13:10:00+00:00",
            },
        )


def _initialize_through_migration(db_path, last_version):
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        migration_root = resources.files("pdi.storage.migrations")
        for migration in sorted(migration_root.iterdir(), key=lambda item: item.name):
            if not migration.name.endswith(".sql"):
                continue
            version = migration.name.split("_", 1)[0]
            if version > last_version:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )
        connection.commit()

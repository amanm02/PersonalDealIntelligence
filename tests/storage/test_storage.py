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
    get_banking_run,
    initialize_database,
    insert_banking_deal,
    insert_banking_run,
    insert_raw_snapshot,
    insert_source_record,
    insert_status_event,
    list_banking_deals,
    list_banking_runs,
    load_seed_fixture,
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
            "banking_runs",
            "banking_run_locks",
            "deal_status_events",
            "deal_change_events",
        }.issubset(table_names)
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0] == 5


def test_migrations_are_idempotent(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    initialize_database(db_path)
    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0] == 5


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

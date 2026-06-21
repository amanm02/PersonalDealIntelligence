import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from pdi.storage import (
    acquire_banking_run_lock,
    initialize_database,
    insert_banking_deal,
    insert_banking_run,
    insert_deal_change_event,
    list_deal_status_events,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(db_path, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "pdi", "--db", str(db_path), *args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def seed_deal(db_path, **overrides):
    values = {
        "canonical_key": overrides.pop("canonical_key", "fixture-checking"),
        "title": overrides.pop("title", "Fixture Bank $300 Checking Bonus"),
        "institution_name": overrides.pop("institution_name", "Fixture Bank"),
        "subcategory": overrides.pop("subcategory", "checking_bonus"),
        "bonus_amount_cents": overrides.pop("bonus_amount_cents", 30000),
        "source_url": overrides.pop("source_url", "https://example.test/fixture"),
        "source_name": overrides.pop("source_name", "Fixture Source"),
        "discovered_at": overrides.pop(
            "discovered_at",
            "2026-06-17T12:00:00+00:00",
        ),
        "last_seen_at": overrides.pop(
            "last_seen_at",
            "2026-06-17T12:00:00+00:00",
        ),
        "expires_at": overrides.pop("expires_at", _days_from_now(60)),
        "application_deadline": overrides.pop("application_deadline", None),
        "status": overrides.pop("status", "new"),
        "confidence_score": overrides.pop("confidence_score", 0.9),
        "terms": overrides.pop(
            "terms",
            {
                "direct_deposit_required": True,
                "direct_deposit_minimum_cents": 100000,
                "minimum_deposit_amount_cents": None,
                "minimum_balance_required_cents": None,
                "balance_hold_days": 90,
                "monthly_fee_cents": 0,
                "new_customer_only": True,
                "state_restrictions": [],
            },
        ),
    }
    values.update(overrides)
    return insert_banking_deal(db_path, values)


def test_list_deals_by_status(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path, canonical_key="new", status="new")
    seed_deal(
        db_path,
        canonical_key="watching",
        title="Fixture Bank $500 Savings Bonus",
        subcategory="savings_bonus",
        status="watching",
    )

    result = run_cli(
        db_path,
        "banking",
        "list",
        "--status",
        "watching",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["status"] for row in rows] == ["watching"]
    assert rows[0]["subcategory"] == "savings_bonus"


def test_show_deal_includes_score_and_terms(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(db_path)

    result = run_cli(db_path, "banking", "show", str(deal_id))

    assert result.returncode == 0, result.stderr
    assert "Score:" in result.stdout
    assert "direct_deposit_required" in result.stdout
    assert "Fixture Bank $300 Checking Bonus" in result.stdout
    assert "verify final terms on the official institution page" in result.stdout


def test_update_status_creates_event_record(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(db_path)

    result = run_cli(
        db_path,
        "banking",
        "update-status",
        str(deal_id),
        "in_progress",
        "--note",
        "Reviewing official page.",
    )

    assert result.returncode == 0, result.stderr
    assert "status to in_progress" in result.stdout
    events = list_deal_status_events(db_path, deal_id=deal_id)
    assert events[-1]["new_status"] == "in_progress"
    assert events[-1]["note"] == "Reviewing official page."


def test_review_needed_returns_missing_data_deals(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path, canonical_key="complete")
    missing_id = seed_deal(
        db_path,
        canonical_key="missing",
        title="Missing Terms Checking Bonus",
        terms={
            "direct_deposit_required": None,
            "monthly_fee_cents": 0,
            "terms_json": {"missing_fields": ["direct_deposit_required"]},
        },
    )

    result = run_cli(db_path, "banking", "review-needed", "--format", "json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert {row["id"] for row in rows} == {missing_id}
    assert rows[0]["recommended_action"] == "needs_more_info"


def test_review_needed_returns_conflicting_deals(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(db_path, canonical_key="conflict")
    insert_deal_change_event(
        db_path,
        deal_id,
        "canonical_field_changed",
        {
            "direct_deposit_required": {
                "old_value": True,
                "candidate_value": False,
                "selected_value": False,
                "reason": "candidate_higher_confidence",
            }
        },
    )

    result = run_cli(db_path, "banking", "review-needed", "--format", "json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert {row["id"] for row in rows} == {deal_id}
    assert rows[0]["needs_review"] is True


def test_expiring_filter_works(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    soon_id = seed_deal(
        db_path,
        canonical_key="soon",
        expires_at=_days_from_now(10),
    )
    seed_deal(
        db_path,
        canonical_key="later",
        title="Later Savings Bonus",
        subcategory="savings_bonus",
        expires_at=_days_from_now(45),
    )

    result = run_cli(db_path, "banking", "expiring", "--days", "14", "--format", "json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [soon_id]


def test_search_free_text_matches_terms_and_source_context(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(
        db_path,
        terms={
            "direct_deposit_required": True,
            "monthly_fee_cents": 0,
            "monthly_fee_waiver_terms": "waived direct deposit",
        },
        source_name="Demo Checking Source",
    )

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--query",
        "waived direct",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [deal_id]
    assert rows[0]["match_reason"] == "matched query 'waived direct'."
    assert rows[0]["source_name"] == "Demo Checking Source"


def test_search_structured_filters_work(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path, canonical_key="checking")
    savings_id = seed_deal(
        db_path,
        canonical_key="savings",
        title="Fixture Bank $500 Savings Bonus",
        subcategory="savings_bonus",
        bonus_amount_cents=50000,
        status="watching",
    )

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--institution",
        "Fixture",
        "--subcategory",
        "savings_bonus",
        "--min-bonus",
        "400",
        "--min-net-value",
        "450",
        "--score-band",
        "high",
        "--recommended-action",
        "review_now",
        "--status",
        "watching",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [savings_id]
    assert rows[0]["bonus_amount_cents"] >= 40000
    assert rows[0]["estimated_net_value_cents"] >= 45000
    assert "subcategory savings_bonus" in rows[0]["match_reason"]


def test_search_expiring_and_needs_review_filters_work(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path, canonical_key="complete", expires_at=_days_from_now(40))
    review_id = seed_deal(
        db_path,
        canonical_key="review",
        title="Review Needed Checking Bonus",
        expires_at=_days_from_now(7),
        terms={
            "direct_deposit_required": None,
            "monthly_fee_cents": 0,
            "terms_json": {"missing_fields": ["direct_deposit_required"]},
        },
    )

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--expiring-days",
        "14",
        "--needs-review",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [review_id]
    assert rows[0]["needs_review"] is True
    assert "expires within 14 days" in rows[0]["match_reason"]


def test_search_results_are_ranked_by_score_net_value_bonus_and_id(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    lower_id = seed_deal(
        db_path,
        canonical_key="lower",
        title="Lower Value Checking Bonus",
        bonus_amount_cents=30000,
    )
    higher_id = seed_deal(
        db_path,
        canonical_key="higher",
        title="Higher Value Checking Bonus",
        bonus_amount_cents=80000,
    )

    result = run_cli(db_path, "banking", "search", "--format", "json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [higher_id, lower_id]
    assert rows[0]["score_0_to_100"] >= rows[1]["score_0_to_100"]
    assert rows[0]["estimated_net_value_cents"] > rows[1]["estimated_net_value_cents"]


def test_search_json_output_includes_match_reason_and_source_fields(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(
        db_path,
        source_name="Fixture Source Label",
        source_url="https://example.test/search-source",
    )

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--query",
        "checking",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert rows[0]["id"] == deal_id
    assert rows[0]["match_reason"] == "matched query 'checking'."
    assert rows[0]["source_name"] == "Fixture Source Label"
    assert rows[0]["source_url"] == "https://example.test/search-source"


def test_find_alias_matches_search_shape(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(db_path)

    result = run_cli(
        db_path,
        "banking",
        "find",
        "--query",
        "checking",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [deal_id]
    assert {"match_reason", "source_name", "source_url"}.issubset(rows[0])


def test_json_output_works(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(db_path)

    result = run_cli(db_path, "banking", "show", str(deal_id), "--format", "json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["id"] == deal_id
    assert payload["score"]["score_band"] == "high"
    assert payload["requirements"]["direct_deposit_required"] is True


def test_digest_command_writes_json_output(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    output_path = tmp_path / "digest.json"
    initialize_database(db_path)
    deal_id = seed_deal(db_path, expires_at="2026-12-31")

    result = run_cli(
        db_path,
        "banking",
        "digest",
        "--format",
        "json",
        "--output",
        str(output_path),
        "--as-of",
        "2026-06-18",
    )

    assert result.returncode == 0, result.stderr
    assert "Generated banking digest" in result.stdout
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["as_of"] == "2026-06-18"
    assert [item["deal_id"] for item in payload["sections"]["Review Now"]] == [
        deal_id
    ]


def test_digest_command_defaults_to_markdown_output(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    output_path = tmp_path / "digest.md"
    initialize_database(db_path)
    seed_deal(db_path, expires_at="2026-06-25")

    result = run_cli(
        db_path,
        "banking",
        "digest",
        "--output",
        str(output_path),
        "--as-of",
        "2026-06-18",
        "--dry-run-notifications",
    )

    assert result.returncode == 0, result.stderr
    rendered = output_path.read_text(encoding="utf-8")
    assert "# Banking Deal Digest" in rendered
    assert "## Expiring Soon" in rendered
    assert "Notification Dry Run" in rendered


def test_run_defaults_to_dry_run_without_durable_deal_or_digest_changes(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    digest_path = tmp_path / "dry-run-digest.md"
    initialize_database(db_path)
    before_counts = workflow_table_counts(db_path)

    result = run_cli(
        db_path,
        "banking",
        "run",
        "--digest-output",
        str(digest_path),
        "--as-of",
        "2026-06-18",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "succeeded"
    assert payload["dry_run"] is True
    assert payload["digest_path"] is None
    assert payload["metadata"]["would_be_digest_path"] == str(digest_path)
    assert payload["metadata"]["digest_written"] is False
    assert payload["source_count"] == 8
    assert workflow_table_counts(db_path) == before_counts
    assert not digest_path.exists()


def test_run_execute_persists_workflow_and_digest(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    digest_path = tmp_path / "run-digest.md"

    result = run_cli(
        db_path,
        "banking",
        "run",
        "--execute",
        "--digest-output",
        str(digest_path),
        "--as-of",
        "2026-06-18",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "succeeded"
    assert payload["dry_run"] is False
    assert payload["digest_path"] == str(digest_path)
    assert payload["canonical_deal_count"] == 5
    assert digest_path.exists()
    assert workflow_table_counts(db_path)["banking_deals"] == 5


def test_runs_and_run_status_return_recorded_run(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    run_result = run_cli(
        db_path,
        "banking",
        "run",
        "--dry-run",
        "--as-of",
        "2026-06-18",
        "--format",
        "json",
    )
    assert run_result.returncode == 0, run_result.stderr

    runs_result = run_cli(db_path, "banking", "runs", "--format", "json")
    assert runs_result.returncode == 0, runs_result.stderr
    runs = json.loads(runs_result.stdout)
    run_id = runs[0]["id"]

    status_result = run_cli(
        db_path,
        "banking",
        "run-status",
        str(run_id),
        "--format",
        "json",
    )

    assert status_result.returncode == 0, status_result.stderr
    status = json.loads(status_result.stdout)
    assert status["id"] == run_id
    assert status["status"] == "succeeded"
    assert status["dry_run"] is True


def test_run_records_blocked_status_without_taking_over_existing_lock(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    locked_run_id = insert_banking_run(db_path, dry_run=True)
    assert acquire_banking_run_lock(db_path, locked_run_id) is True

    result = run_cli(
        db_path,
        "banking",
        "run",
        "--dry-run",
        "--format",
        "json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["errors"] == ["another banking run is already active"]
    with sqlite3.connect(db_path) as connection:
        lock = connection.execute(
            "SELECT run_id FROM banking_run_locks WHERE lock_name = 'banking_run'"
        ).fetchone()
    assert lock[0] == locked_run_id


def test_sources_list_and_validate_show_public_pilot_metadata(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    list_result = run_cli(
        db_path,
        "banking",
        "sources",
        "list",
        "--group",
        "public-pilot",
        "--format",
        "json",
    )

    assert list_result.returncode == 0, list_result.stderr
    sources = json.loads(list_result.stdout)
    assert len(sources) == 1
    assert sources[0]["source_id"] == "public-pilot-placeholder-rss"
    assert sources[0]["source_group"] == "public-pilot"
    assert sources[0]["enabled"] is False
    assert sources[0]["blocked_reason"] == "disabled"

    validate_result = run_cli(
        db_path,
        "banking",
        "sources",
        "validate",
        "--format",
        "json",
    )

    assert validate_result.returncode == 0, validate_result.stderr
    payload = json.loads(validate_result.stdout)
    assert payload["status"] == "valid"
    assert payload["public_pilot_source_count"] == 1
    assert payload["enabled_public_pilot_source_count"] == 0


def test_public_pilot_run_requires_dry_run_or_live_confirmation(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    result = run_cli(
        db_path,
        "banking",
        "run",
        "--sources",
        "public-pilot",
        "--format",
        "json",
    )

    assert result.returncode == 1
    assert (
        "Public pilot live collection requires --confirm-live or use --dry-run."
        in result.stdout
    )


def test_public_pilot_dry_run_plans_without_network(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    result = run_cli(
        db_path,
        "banking",
        "run",
        "--dry-run",
        "--sources",
        "public-pilot",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    public_pilot = payload["metadata"]["public_pilot"]
    assert payload["dry_run"] is True
    assert public_pilot["network_fetch_attempted"] is False
    assert public_pilot["enabled_source_count"] == 0
    assert public_pilot["message"] == "No enabled public pilot sources configured."


def test_public_pilot_confirm_live_with_no_enabled_sources_is_clean(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    result = run_cli(
        db_path,
        "banking",
        "run",
        "--sources",
        "public-pilot",
        "--confirm-live",
    )

    assert result.returncode == 0, result.stderr
    assert "No enabled public pilot sources configured." in result.stdout


def _days_from_now(days):
    return (date.today() + timedelta(days=days)).isoformat()


def workflow_table_counts(db_path):
    tables = (
        "source_records",
        "raw_deal_snapshots",
        "banking_deal_candidates",
        "banking_deals",
        "banking_deal_source_links",
        "deal_change_events",
        "deal_status_events",
    )
    with sqlite3.connect(db_path) as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from pdi.storage import (
    initialize_database,
    insert_banking_deal,
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


def _days_from_now(days):
    return (date.today() + timedelta(days=days)).isoformat()

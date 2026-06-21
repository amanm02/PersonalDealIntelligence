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


def test_search_free_text_matches_terms(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(
        db_path,
        canonical_key="fee-waiver",
        terms={
            "direct_deposit_required": True,
            "direct_deposit_minimum_cents": 100000,
            "monthly_fee_cents": 1200,
            "monthly_fee_waiver_terms": "waived with qualifying direct deposit",
            "new_customer_only": True,
            "state_restrictions": [],
        },
    )
    seed_deal(
        db_path,
        canonical_key="savings",
        title="Fixture Bank $500 Savings Bonus",
        subcategory="savings_bonus",
        bonus_amount_cents=50000,
        terms={"monthly_fee_cents": 0},
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


def test_search_institution_filter_works(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path, canonical_key="fixture-bank")
    other_id = seed_deal(
        db_path,
        canonical_key="other-bank",
        title="Other Bank $400 Checking Bonus",
        institution_name="Other Bank",
        bonus_amount_cents=40000,
    )

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--institution",
        "Other",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [other_id]
    assert "matched institution 'Other'" in rows[0]["match_reason"]


def test_search_subcategory_filter_works(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path, canonical_key="checking")
    savings_id = seed_deal(
        db_path,
        canonical_key="savings",
        title="Fixture Bank $500 Savings Bonus",
        subcategory="savings_bonus",
        bonus_amount_cents=50000,
        terms={"monthly_fee_cents": 0},
    )

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--subcategory",
        "savings_bonus",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [savings_id]
    assert rows[0]["subcategory"] == "savings_bonus"


def test_search_minimum_bonus_and_net_value_filters_work(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path, canonical_key="small")
    large_id = seed_deal(
        db_path,
        canonical_key="large",
        title="Fixture Bank $800 Savings Bonus",
        subcategory="savings_bonus",
        bonus_amount_cents=80000,
        terms={
            "minimum_balance_required_cents": 100000,
            "balance_hold_days": 30,
            "monthly_fee_cents": 0,
            "new_customer_only": False,
            "state_restrictions": [],
        },
    )

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--min-bonus",
        "500",
        "--min-net-value",
        "700",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [large_id]
    assert rows[0]["bonus_amount_cents"] == 80000
    assert rows[0]["estimated_net_value_cents"] >= 70000


def test_search_expiring_filter_works(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    soon_id = seed_deal(db_path, canonical_key="soon", expires_at=_days_from_now(7))
    seed_deal(db_path, canonical_key="later", expires_at=_days_from_now(60))

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--expiring-days",
        "14",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [soon_id]
    assert rows[0]["match_reason"] == "expires within 14 days."


def test_search_needs_review_surfaces_conflicts(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path, canonical_key="complete")
    conflict_id = seed_deal(db_path, canonical_key="conflict")
    insert_deal_change_event(
        db_path,
        conflict_id,
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

    result = run_cli(
        db_path,
        "banking",
        "search",
        "--needs-review",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [conflict_id]
    assert rows[0]["review_indicator"] == "conflict"


def test_search_results_are_ranked_by_score_and_net_value(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    lower_id = seed_deal(db_path, canonical_key="lower", bonus_amount_cents=30000)
    higher_id = seed_deal(
        db_path,
        canonical_key="higher",
        title="Fixture Bank $900 Savings Bonus",
        subcategory="savings_bonus",
        bonus_amount_cents=90000,
        terms={
            "minimum_balance_required_cents": 100000,
            "balance_hold_days": 30,
            "monthly_fee_cents": 0,
            "new_customer_only": False,
            "state_restrictions": [],
        },
    )

    result = run_cli(db_path, "banking", "search", "--format", "json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [higher_id, lower_id]
    assert rows[0]["estimated_net_value_cents"] > rows[1]["estimated_net_value_cents"]


def test_search_json_output_includes_match_and_source_fields(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(db_path)

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
    assert [row["id"] for row in rows] == [deal_id]
    assert rows[0]["source_name"] == "Fixture Source"
    assert rows[0]["source_url"] == "https://example.test/fixture"
    assert rows[0]["match_reason"] == "matched query 'checking'."


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

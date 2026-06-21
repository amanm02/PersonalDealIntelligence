import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from pdi.storage import (
    acquire_banking_run_lock,
    initialize_database,
    insert_banking_deal_candidate,
    insert_banking_deal,
    insert_banking_deal_source_link,
    insert_banking_run,
    insert_deal_change_event,
    insert_raw_snapshot,
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


def test_show_json_includes_snapshot_metadata_and_field_evidence(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    raw_text = "Fixture Bank offers a $300 checking bonus with direct deposit."
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://fixture-show",
            "source_name": "Fixture Show Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": raw_text,
            "raw_payload_json": {"fixture_id": "show-evidence"},
            "collector_name": "fixture",
        },
    )
    deal_id = seed_deal(
        db_path,
        raw_snapshot_id=snapshot_id,
        expires_at=None,
        terms={
            "direct_deposit_required": True,
            "direct_deposit_minimum_cents": None,
            "minimum_deposit_amount_cents": None,
            "minimum_balance_required_cents": None,
            "balance_hold_days": None,
            "monthly_fee_cents": None,
            "new_customer_only": None,
            "state_restrictions": None,
        },
    )
    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Fixture Bank $300 Checking Bonus",
            "institution_name": "Fixture Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "direct_deposit_required": True,
            "source_name": "Fixture Show Source",
            "source_url": "manual://fixture-show",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "evidence_spans": [],
            "missing_fields": [],
            "confidence_score": 0.9,
        },
    )
    insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Fixture Show Source",
            "source_url": "manual://fixture-show",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.9,
            "evidence": [
                {
                    "field": "bonus_amount_cents",
                    "text": "$300",
                    "start": 22,
                    "end": 26,
                    "extracted_value": 30000,
                    "extraction_method": "fixture_parser",
                },
                {
                    "field": "direct_deposit_required",
                    "text": "direct deposit",
                    "start": 47,
                    "end": 61,
                    "extracted_value": True,
                    "extraction_method": "fixture_parser",
                },
            ],
        },
    )

    result = run_cli(db_path, "banking", "show", str(deal_id), "--format", "json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    snapshot = payload["source_snapshots"][0]
    assert snapshot["id"] == snapshot_id
    assert snapshot["content_hash"]
    assert snapshot["collector_name"] == "fixture"
    assert snapshot["raw_payload_metadata"] == {
        "keys": ["fixture_id"],
        "field_count": 1,
    }
    assert snapshot["raw_text_length"] == len(raw_text)
    assert "raw_text" not in snapshot
    assert "raw_payload" not in snapshot
    evidence = {item["field"]: item for item in payload["field_evidence"]}
    assert evidence["bonus_amount_cents"]["extracted_value"] == 30000
    assert evidence["bonus_amount_cents"]["content_hash"] == snapshot["content_hash"]
    assert evidence["direct_deposit_required"]["extracted_value"] is True
    assert payload["missing_evidence_warnings"] == []


def test_show_text_surfaces_missing_evidence_warning(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot_id = insert_raw_snapshot(
        db_path,
        {
            "source_url": "manual://fixture-missing-evidence",
            "source_name": "Fixture Missing Evidence Source",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "raw_text": "Fixture Bank offers a $300 checking bonus.",
            "collector_name": "fixture",
        },
    )
    deal_id = seed_deal(db_path, raw_snapshot_id=snapshot_id)
    candidate_id = insert_banking_deal_candidate(
        db_path,
        {
            "raw_snapshot_id": snapshot_id,
            "title": "Fixture Bank $300 Checking Bonus",
            "institution_name": "Fixture Bank",
            "subcategory": "checking_bonus",
            "bonus_amount_cents": 30000,
            "direct_deposit_required": True,
            "source_name": "Fixture Missing Evidence Source",
            "source_url": "manual://fixture-missing-evidence",
            "source_authority": "secondary",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "evidence_spans": [],
            "missing_fields": [],
            "confidence_score": 0.9,
        },
    )
    insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate_id,
            "raw_snapshot_id": snapshot_id,
            "source_name": "Fixture Missing Evidence Source",
            "source_url": "manual://fixture-missing-evidence",
            "source_authority": "secondary",
            "retrieved_at": "2026-06-17T12:00:00+00:00",
            "confidence_score": 0.9,
            "evidence": [
                {
                    "field": "bonus_amount_cents",
                    "text": "$300",
                    "start": 22,
                    "end": 26,
                    "extracted_value": 30000,
                }
            ],
        },
    )

    result = run_cli(db_path, "banking", "show", str(deal_id))

    assert result.returncode == 0, result.stderr
    assert "Source snapshots:" in result.stdout
    assert "Field evidence:" in result.stdout
    assert "bonus_amount_cents" in result.stdout
    assert "direct_deposit_required has value but no field-level evidence" in result.stdout
    assert "bonus_amount_cents has only secondary-source evidence" in result.stdout
    assert "Fixture Bank offers a $300 checking bonus." not in result.stdout


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
    assert sources[0]["source_class"] == "third_party"
    assert sources[0]["trust_tier"] == "community"
    assert sources[0]["official_source"] is False
    assert sources[0]["deposit_account_source"] is True
    assert sources[0]["brokerage_source"] is True
    assert sources[0]["credit_card_source"] is False
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


def test_sources_list_filters_by_trust_tier_and_credit_card_flag(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    result = run_cli(
        db_path,
        "banking",
        "sources",
        "list",
        "--trust-tier",
        "official",
        "--credit-card",
        "true",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    sources = json.loads(result.stdout)
    assert {source["source_id"] for source in sources} == {
        "seed-issuer-credit-card-detail",
        "seed-issuer-credit-card-terms",
    }
    assert all(source["official_source"] is True for source in sources)


def test_sources_show_includes_onboarding_review(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    result = run_cli(
        db_path,
        "banking",
        "sources",
        "show",
        "seed-issuer-credit-card-detail",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["source_id"] == "seed-issuer-credit-card-detail"
    assert payload["enabled"] is False
    assert payload["onboarding_review"]["safe_default"] is True
    assert payload["onboarding_review"]["onboarding_status"] == "review_required"
    assert (
        "source policy pending review before collection"
        in payload["onboarding_review"]["review_blockers"]
    )


def test_sources_onboarding_check_filters_review_required_sources(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    result = run_cli(
        db_path,
        "banking",
        "sources",
        "onboarding-check",
        "--review-required",
        "--credit-card",
        "true",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["review_required_count"] == 4
    assert payload["invalid_count"] == 0
    assert {source["source_id"] for source in payload["sources"]} == {
        "seed-issuer-credit-card-detail",
        "seed-issuer-credit-card-terms",
        "seed-third-party-card-offers-rss",
        "seed-user-card-newsletter-export",
    }
    assert all(source["live_collection_enabled"] is False for source in payload["sources"])


def test_sources_scaffold_prints_disabled_yaml_without_writing_config(tmp_path):
    db_path = tmp_path / "pdi.sqlite"

    result = run_cli(
        db_path,
        "banking",
        "sources",
        "scaffold",
        "--id",
        "seed-new-card-source",
        "--name",
        "Seed New Card Source",
        "--publisher",
        "Example Issuer",
        "--url",
        "https://example.test/card",
        "--source-type",
        "official_promo_page",
        "--source-class",
        "official",
        "--subcategory",
        "credit_card_signup_bonus",
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load(result.stdout)
    source = payload["sources"][0]
    assert source["source_id"] == "seed-new-card-source"
    assert source["enabled"] is False
    assert source["fixture_enabled"] is False
    assert source["allow_scrape"] is False
    assert source["requires_login"] is False
    assert source["compliance_status"] == "pending_review"
    assert "password" not in result.stdout


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
    assert public_pilot["planned_sources"][0]["collection_status"] == "disabled"


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


def test_public_pilot_confirm_live_bad_url_fails_closed_with_json_metadata(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    config_path = tmp_path / "banking_sources.yaml"
    config_path.write_text(
        """sources:
  - source_id: "public-pilot-bad-url"
    source_group: "public-pilot"
    publisher_name: "Public Pilot Bad URL Publisher"
    name: "Public Pilot Bad URL RSS"
    url: "feed://user:secret@pilot-public.example.test/rss.xml?token=secret"
    source_type: "rss_feed"
    source_class: "third_party"
    category_scope:
      - "banking"
    subcategory_scope:
      - "checking_bonus"
    coverage_purpose: "Bad URL public-pilot test source."
    trust_tier: "community"
    official_source: false
    deposit_account_source: true
    brokerage_source: false
    credit_card_source: false
    fixture_enabled: false
    source_priority: 50
    region_scope:
      - "US"
    enabled: true
    collection_method: "rss_feed"
    max_frequency_hours: 48
    requires_login: false
    allow_scrape: false
    allow_api: false
    allow_rss: true
    allow_email_parse: false
    robots_policy_notes: "RSS only; no scraping."
    terms_policy_notes: "Bad URL test source."
    rate_limit_notes: "At most once every 48 hours."
    compliance_status: "approved"
    last_reviewed_at: "2026-06-21"
    notes: "CLI fetch failure metadata test source."
""",
        encoding="utf-8",
    )

    result = run_cli(
        db_path,
        "banking",
        "run",
        "--sources",
        "public-pilot",
        "--confirm-live",
        "--source-config",
        str(config_path),
        "--format",
        "json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    public_pilot = payload["metadata"]["public_pilot"]
    assert public_pilot["network_fetch_attempted"] is True
    assert "secret" not in str(public_pilot)
    source = public_pilot["planned_sources"][0]
    assert source["collection_status"] == "fetch_failed"
    assert source["fetch_result"]["error_type"] == "bad_url"


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

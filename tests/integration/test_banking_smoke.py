import json
import os
import subprocess
import sys
from pathlib import Path

from pdi.scoring import score_banking_deal
from pdi.smoke import run_offline_banking_smoke
from pdi.storage import (
    list_banking_deal_candidates,
    list_banking_deals,
    list_deal_change_events,
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


def test_offline_banking_smoke_runs_full_fixture_flow(tmp_path):
    db_path = tmp_path / "pdi-smoke.sqlite"
    digest_path = tmp_path / "offline-smoke-digest.md"

    summary = run_offline_banking_smoke(
        db_path,
        digest_output=digest_path,
        reset_db=True,
    )

    assert summary.sources == 8
    assert summary.raw_snapshots == 8
    assert summary.candidates == 8
    assert summary.rejected_candidates == 1
    assert summary.canonical_deals == 5
    assert summary.duplicate_merges == 2
    assert summary.conflicts == 1
    assert summary.scored_deals == 5
    assert summary.expired_scored_deals == 1
    assert digest_path.exists()
    assert "# Banking Deal Digest" in digest_path.read_text(encoding="utf-8")


def test_offline_smoke_rejects_non_deal_fixture(tmp_path):
    db_path = tmp_path / "pdi-smoke.sqlite"
    run_offline_banking_smoke(
        db_path,
        digest_output=tmp_path / "digest.md",
        reset_db=True,
    )

    candidates = list_banking_deal_candidates(db_path)
    rejected = [candidate for candidate in candidates if candidate["rejected"]]

    assert len(rejected) == 1
    assert rejected[0]["source_name"] == "Offline Smoke Non Deal"
    assert "No explicit banking promotion terms found" in rejected[0]["rejection_reason"]


def test_offline_smoke_collapses_duplicate_and_conflicting_checking(tmp_path):
    db_path = tmp_path / "pdi-smoke.sqlite"
    run_offline_banking_smoke(
        db_path,
        digest_output=tmp_path / "digest.md",
        reset_db=True,
    )

    northstar_deals = [
        deal
        for deal in list_banking_deals(db_path)
        if deal["institution_name"] == "Northstar Mock Bank"
    ]
    events = list_deal_change_events(db_path, deal_id=int(northstar_deals[0]["id"]))

    assert len(northstar_deals) == 1
    assert northstar_deals[0]["status"] == "needs_review"
    assert any("direct_deposit_required" in event["changed_fields_json"] for event in events)


def test_offline_smoke_scores_all_canonical_deals_and_expired_fixture(tmp_path):
    db_path = tmp_path / "pdi-smoke.sqlite"
    run_offline_banking_smoke(
        db_path,
        digest_output=tmp_path / "digest.md",
        reset_db=True,
    )

    deals = list_banking_deals(db_path)
    scores = {
        deal["institution_name"]: score_banking_deal(db_path, int(deal["id"]))
        for deal in deals
    }

    assert len(scores) == len(deals) == 5
    assert scores["Sunset Mock Bank"].recommended_action == "expired"
    assert all(deal["estimated_net_value_cents"] is not None for deal in deals)


def test_offline_smoke_summary_is_deterministic_for_fixed_fixtures(tmp_path):
    first_db = tmp_path / "first.sqlite"
    second_db = tmp_path / "second.sqlite"
    first = run_offline_banking_smoke(
        first_db,
        digest_output=tmp_path / "first.md",
        reset_db=True,
    )
    second = run_offline_banking_smoke(
        second_db,
        digest_output=tmp_path / "second.md",
        reset_db=True,
    )

    first_payload = first.to_dict()
    second_payload = second.to_dict()
    first_payload["digest_path"] = "<digest>"
    second_payload["digest_path"] = "<digest>"

    assert first_payload == second_payload


def test_smoke_test_cli_outputs_json_summary(tmp_path):
    db_path = tmp_path / "pdi-smoke.sqlite"
    digest_path = tmp_path / "offline-smoke-digest.md"

    result = run_cli(
        db_path,
        "banking",
        "smoke-test",
        "--digest-output",
        str(digest_path),
        "--as-of",
        "2026-06-18",
        "--reset-db",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["sources"] == 8
    assert payload["canonical_deals"] == 5
    assert payload["conflicts"] == 1
    assert payload["digest_path"] == str(digest_path)
    assert digest_path.exists()


def test_smoke_test_cli_refuses_existing_database_without_reset(tmp_path):
    db_path = tmp_path / "pdi-smoke.sqlite"
    digest_path = tmp_path / "offline-smoke-digest.md"
    run_offline_banking_smoke(
        db_path,
        digest_output=digest_path,
        reset_db=True,
    )

    result = run_cli(
        db_path,
        "banking",
        "smoke-test",
        "--digest-output",
        str(digest_path),
        "--format",
        "json",
    )

    assert result.returncode == 1
    assert "pass --reset-db to replace it" in result.stdout

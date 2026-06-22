import json
import os
import subprocess
import sys
from pathlib import Path

from pdi.qa_benchmark import run_banking_qa_benchmark
from pdi.storage import list_banking_score_records


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


def test_qa_benchmark_json_output_is_offline_and_deterministic(tmp_path):
    first = run_cli(
        tmp_path / "pdi-demo-qa-1.sqlite",
        "banking",
        "qa-benchmark",
        "--reset-db",
        "--json",
    )
    second = run_cli(
        tmp_path / "pdi-demo-qa-2.sqlite",
        "banking",
        "qa-benchmark",
        "--reset-db",
        "--format",
        "json",
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)

    assert first_payload == second_payload
    assert first_payload["offline_only"] is True
    assert first_payload["verification_status"] == "pass"
    assert first_payload["summary"]["raw_snapshots"] == 11
    assert first_payload["summary"]["canonical_deals"] == 8
    assert first_payload["sections"]["deposit"]["expected_deals_missed"] == []
    assert first_payload["sections"]["credit_card"]["status"] == "pending_runtime"


def test_qa_benchmark_table_output_reports_core_checks(tmp_path):
    result = run_cli(
        tmp_path / "pdi-demo-qa.sqlite",
        "banking",
        "qa-benchmark",
        "--reset-db",
    )

    assert result.returncode == 0, result.stderr
    assert "Offline banking QA benchmark complete." in result.stdout
    assert "verification_status" in result.stdout
    assert "deposit" in result.stdout
    assert "pending_runtime" in result.stdout


def test_qa_benchmark_can_be_repeated_against_same_database(tmp_path):
    db_path = tmp_path / "pdi-demo-qa.sqlite"
    table_result = run_cli(
        db_path,
        "banking",
        "qa-benchmark",
    )
    json_result = run_cli(
        db_path,
        "banking",
        "qa-benchmark",
        "--json",
    )

    assert table_result.returncode == 0, table_result.stderr
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["verification_status"] == "pass"
    assert payload["summary"]["raw_snapshots"] == 11
    assert payload["summary"]["canonical_deals"] == 8
    assert payload["summary"]["duplicate_merges"] == 2
    assert payload["summary"]["conflicts"] == 1


def test_qa_benchmark_deposit_category_runs_runnable_fixture_scope(tmp_path):
    result = run_cli(
        tmp_path / "pdi-demo-qa.sqlite",
        "banking",
        "qa-benchmark",
        "--category",
        "deposit",
        "--reset-db",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["category"] == "deposit"
    assert payload["verification_status"] == "pass"
    assert set(payload["sections"]) == {"deposit"}
    assert "brokerage_bonus" in payload["sections"]["deposit"]["subcategories_found"]


def test_qa_benchmark_persists_score_records(tmp_path):
    db_path = tmp_path / "pdi-demo-qa.sqlite"

    payload = run_banking_qa_benchmark(db_path, reset_db=True)

    assert payload["verification_status"] == "pass"
    assert len(list_banking_score_records(db_path)) == (
        payload["summary"]["canonical_deals"]
    )


def test_qa_benchmark_credit_card_category_reports_deferred_runtime(tmp_path):
    result = run_cli(
        tmp_path / "pdi-demo-qa.sqlite",
        "banking",
        "qa-benchmark",
        "--category",
        "credit_card",
        "--reset-db",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["category"] == "credit_card"
    assert payload["verification_status"] == "pending"
    assert payload["summary"]["raw_snapshots"] == 0
    assert payload["sections"]["credit_card"]["status"] == "pending_runtime"


def test_qa_benchmark_fails_when_expected_deal_is_missing(tmp_path):
    payload = run_banking_qa_benchmark(
        tmp_path / "pdi-demo-qa.sqlite",
        reset_db=True,
        expected_deposit_deals=("Missing Demo Bank",),
    )

    assert payload["verification_status"] == "fail"
    assert payload["sections"]["deposit"]["expected_deals_missed"] == [
        "Missing Demo Bank"
    ]
    assert "expected_deals_found" in payload["failures"]

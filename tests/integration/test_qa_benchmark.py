import json
import os
import subprocess
import sys
from pathlib import Path

from pdi.qa_benchmark import run_banking_qa_benchmark


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


def check_by_name(payload, name):
    return next(
        check
        for check in payload["supported_checks"]
        if check["name"] == name
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
    assert first_payload["scenario_coverage"]["missing_scenarios"] == []
    assert first_payload["scenario_coverage"]["scenario_counts"]["active_checking"] == 1
    assert (
        first_payload["scenario_coverage"]["scenario_counts"][
            "disabled_or_disallowed_source"
        ]
        == 1
    )
    assert first_payload["sections"]["deposit"]["expected_deals_missed"] == []
    assert first_payload["sections"]["deposit"]["status"] == "pass"
    assert first_payload["sections"]["deposit"]["checks"]["expected_deals_found"]
    assert (
        first_payload["sections"]["deposit"]["reason_code"]
        == "supported_checks_passed"
    )
    assert [
        check["name"]
        for check in first_payload["sections"]["deposit"]["supported_checks"]
    ] == [
        "expected_deals_found",
        "unexpected_deals_absent",
        "expected_subcategories_present",
        "duplicate_offer_merged",
        "conflicting_terms_surfaced",
        "non_deal_suppressed",
        "expired_offer_flagged",
        "low_value_offer_flagged",
        "ambiguous_terms_surfaced",
        "scores_persisted",
        "expected_scenarios_present",
    ]
    expected_deals_check = check_by_name(first_payload, "expected_deals_found")
    assert expected_deals_check["section"] == "deposit"
    assert expected_deals_check["status"] == "pass"
    assert expected_deals_check["actual"] == expected_deals_check["expected"]
    assert expected_deals_check["reason"]
    assert first_payload["sections"]["credit_card"]["status"] == "pending_runtime"
    assert first_payload["sections"]["credit_card"]["reason_code"] == (
        "credit_card_coverage_deferred_to_24d"
    )
    assert first_payload["sections"]["rules_engine"] == {
        "dependency": "#37",
        "failures": [],
        "reason": "Eligibility and requirements rules-engine checks remain deferred to #37.",
        "reason_code": "rules_engine_deferred",
        "status": "skipped_dependency",
    }


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
    assert "supported_checks_passed" in result.stdout
    assert "skipped_dependency" in result.stdout
    assert "Supported checks:" in result.stdout
    assert "expected_deals_found" in result.stdout
    assert "expected_scenarios_present" in result.stdout


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
    assert payload["sections"]["deposit"]["reason_code"] == "supported_checks_passed"
    assert payload["scenario_coverage"]["missing_scenarios"] == []
    assert "brokerage_bonus" in payload["sections"]["deposit"]["subcategories_found"]


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
    assert payload["failures"] == []
    assert payload["supported_checks"] == []
    assert payload["sections"]["credit_card"]["status"] == "pending_runtime"
    assert payload["sections"]["credit_card"]["reason_code"] == (
        "credit_card_coverage_deferred_to_24d"
    )


def test_qa_benchmark_fails_when_expected_deal_is_missing(tmp_path):
    payload = run_banking_qa_benchmark(
        tmp_path / "pdi-demo-qa.sqlite",
        reset_db=True,
        expected_deposit_deals=("Missing Demo Bank",),
    )

    assert payload["verification_status"] == "fail"
    assert payload["sections"]["deposit"]["status"] == "fail"
    assert payload["sections"]["deposit"]["reason_code"] == "deposit_checks_failed"
    assert payload["sections"]["deposit"]["expected_deals_missed"] == [
        "Missing Demo Bank"
    ]
    assert "expected_deals_found" in payload["failures"]
    check = check_by_name(payload, "expected_deals_found")
    assert check["status"] == "fail"
    assert check["actual"] == [
        "Cypress Sample Bank",
        "Harbor Demo Brokerage",
        "Lakeside Sample Bank",
        "Northstar Demo Bank",
        "Pioneer Example Bank",
        "Prairie Example Bank",
        "Riverbend Demo Bank",
        "Sunset Demo Bank",
    ]
    assert check["expected"] == ["Missing Demo Bank"]
    assert check["reason"] == (
        "All required deposit and brokerage demo deals should canonicalize."
    )


def test_qa_benchmark_fails_when_expected_scenario_is_missing(tmp_path):
    payload = run_banking_qa_benchmark(
        tmp_path / "pdi-demo-qa.sqlite",
        reset_db=True,
        expected_deposit_scenarios=("missing_scenario",),
    )

    assert payload["verification_status"] == "fail"
    assert payload["sections"]["deposit"]["status"] == "fail"
    assert payload["sections"]["deposit"]["reason_code"] == "deposit_checks_failed"
    assert payload["sections"]["deposit"]["missing_scenarios"] == [
        "missing_scenario"
    ]
    assert "expected_scenarios_present" in payload["sections"]["deposit"]["failures"]
    assert "expected_scenarios_present" in payload["failures"]
    check = check_by_name(payload, "expected_scenarios_present")
    assert check["status"] == "fail"
    assert check["actual"]["missing_scenario"] == 0
    assert check["expected"] == ["missing_scenario"]
    assert check["reason"] == (
        "Every required fixture scenario should be present in the demo manifest."
    )


def test_qa_benchmark_fails_when_duplicate_threshold_is_not_met(tmp_path):
    payload = run_banking_qa_benchmark(
        tmp_path / "pdi-demo-qa.sqlite",
        reset_db=True,
        expected_duplicate_merges_min=3,
    )

    assert payload["verification_status"] == "fail"
    assert "duplicate_offer_merged" in payload["failures"]
    check = check_by_name(payload, "duplicate_offer_merged")
    assert check["status"] == "fail"
    assert check["actual"] == {
        "canonical_deals_for_fixture": 1,
        "duplicate_merges": 2,
    }
    assert check["expected"] == {
        "canonical_deals_for_fixture": 1,
        "duplicate_merges_min": 3,
    }
    assert check["reason"] == (
        "Duplicate fixture mentions should merge into one canonical deal."
    )


def test_qa_benchmark_fails_when_false_positive_deal_appears(tmp_path):
    payload = run_banking_qa_benchmark(
        tmp_path / "pdi-demo-qa.sqlite",
        reset_db=True,
        expected_deposit_deals=(
            "Cypress Sample Bank",
            "Harbor Demo Brokerage",
            "Lakeside Sample Bank",
            "Northstar Demo Bank",
            "Pioneer Example Bank",
            "Prairie Example Bank",
            "Riverbend Demo Bank",
        ),
    )

    assert payload["verification_status"] == "fail"
    assert payload["sections"]["deposit"]["unexpected_deals"] == [
        "Sunset Demo Bank"
    ]
    assert "unexpected_deals_absent" in payload["failures"]
    check = check_by_name(payload, "unexpected_deals_absent")
    assert check["status"] == "fail"
    assert check["actual"] == ["Sunset Demo Bank"]
    assert check["expected"] == []


def test_qa_benchmark_supported_check_order_is_deterministic(tmp_path):
    first = run_banking_qa_benchmark(
        tmp_path / "pdi-demo-qa-1.sqlite",
        reset_db=True,
    )
    second = run_banking_qa_benchmark(
        tmp_path / "pdi-demo-qa-2.sqlite",
        reset_db=True,
    )

    assert [check["name"] for check in first["supported_checks"]] == [
        check["name"] for check in second["supported_checks"]
    ]
    assert first["supported_checks"] == second["supported_checks"]

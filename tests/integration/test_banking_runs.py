import json
import sqlite3

from pdi.runs import run_banking_workflow_once
from pdi.storage import get_banking_run, list_banking_score_records


def test_run_orchestrator_releases_lock_after_successful_execute(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    digest_path = tmp_path / "digest.md"

    run = run_banking_workflow_once(
        db_path,
        dry_run=False,
        digest_output=digest_path,
    )

    stored = get_banking_run(db_path, int(run["id"]))
    with sqlite3.connect(db_path) as connection:
        lock_count = connection.execute(
            "SELECT COUNT(*) FROM banking_run_locks"
        ).fetchone()[0]

    assert run["status"] == "succeeded"
    assert stored["dry_run"] == 0
    assert stored["digest_path"] == str(digest_path)
    assert stored["score_record_count"] == 5
    assert json.loads(stored["score_record_ids_json"]) == [
        record["id"]
        for record in reversed(
            list_banking_score_records(db_path, banking_run_id=int(run["id"]))
        )
    ]
    assert lock_count == 0
    assert digest_path.exists()


def test_run_orchestrator_dry_run_keeps_score_records_temporary(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    digest_path = tmp_path / "dry-run-digest.md"

    run = run_banking_workflow_once(
        db_path,
        dry_run=True,
        digest_output=digest_path,
    )
    stored = get_banking_run(db_path, int(run["id"]))

    assert run["status"] == "succeeded"
    assert stored["dry_run"] == 1
    assert stored["scored_deal_count"] == 5
    assert stored["score_record_count"] == 0
    assert stored["score_record_ids_json"] == "[]"
    assert list_banking_score_records(db_path) == []
    assert not digest_path.exists()


def test_run_orchestrator_failed_execute_keeps_score_record_audit_metadata(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    digest_directory = tmp_path / "digest-directory"
    digest_directory.mkdir()

    run = run_banking_workflow_once(
        db_path,
        dry_run=False,
        digest_output=digest_directory,
    )
    stored = get_banking_run(db_path, int(run["id"]))
    score_records = list_banking_score_records(
        db_path,
        banking_run_id=int(run["id"]),
    )

    assert run["status"] == "failed"
    assert stored["score_record_count"] == len(score_records) == 5
    assert json.loads(stored["score_record_ids_json"]) == [
        record["id"]
        for record in reversed(score_records)
    ]
    assert stored["error_count"] == 1

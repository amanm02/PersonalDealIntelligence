import sqlite3

from pdi.runs import run_banking_workflow_once
from pdi.storage import get_banking_run


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
    assert lock_count == 0
    assert digest_path.exists()

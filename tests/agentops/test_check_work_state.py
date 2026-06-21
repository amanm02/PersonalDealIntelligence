from __future__ import annotations

import subprocess
from pathlib import Path

from tools.agentops.check_work_state import collect_work_state, main, render_work_state


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def make_repo_behind_origin_main(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    git(tmp_path, "init", "--bare", str(remote))

    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "agentops@example.test")
    git(repo, "config", "user.name", "AgentOps Test")
    write(repo / "README.md", "initial\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")

    git(repo, "checkout", "-b", "feature")
    git(repo, "checkout", "main")
    write(repo / "README.md", "initial\nupdated\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "advance main")
    git(repo, "push", "origin", "main")
    git(repo, "fetch", "origin", "main")
    git(repo, "checkout", "feature")
    write(repo / "local.txt", "dirty\n")
    return repo


def test_work_state_reports_branch_dirty_tree_divergence_and_worktree(tmp_path: Path) -> None:
    repo = make_repo_behind_origin_main(tmp_path)

    state = collect_work_state(repo)
    exit_code, lines = render_work_state(state)
    output = "\n".join(lines)

    assert exit_code == 1
    assert f"INFO worktree_path {repo}" in output
    assert "INFO current_branch feature" in output
    assert "FAIL dirty_tree yes (1 entries)" in output
    assert "?? local.txt" in output
    assert "WARN divergence_from_origin/main behind=1 ahead=0" in output
    assert "WARN stale_branch_suspicion branch is 1 commit(s) behind origin/main" in output


def test_work_state_passes_for_clean_branch_at_origin_main(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "agentops@example.test")
    git(repo, "config", "user.name", "AgentOps Test")
    write(repo / "README.md", "initial\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(repo, "fetch", "origin", "main")

    state = collect_work_state(repo)
    exit_code, lines = render_work_state(state)
    output = "\n".join(lines)

    assert exit_code == 0
    assert "OK dirty_tree no" in output
    assert "OK divergence_from_origin/main behind=0 ahead=0" in output
    assert "OK stale_branch_suspicion no" in output


def test_work_state_advisory_mode_reports_but_exits_zero(tmp_path: Path, capsys) -> None:
    repo = make_repo_behind_origin_main(tmp_path)

    exit_code = main(["--repo", str(repo), "--advisory"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "check_work_state: FAIL" in output
    assert "check_work_state: ADVISORY_ONLY" in output


def test_work_state_checks_expected_issue_against_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "agentops@example.test")
    git(repo, "config", "user.name", "AgentOps Test")
    write(repo / "README.md", "initial\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(repo, "checkout", "-b", "codex/issue-016-demo-readiness")

    state = collect_work_state(repo)
    matching_exit, matching_lines = render_work_state(state, expected_issue=16)
    mismatched_exit, mismatched_lines = render_work_state(state, expected_issue=17)

    assert matching_exit == 0
    assert "OK branch_issue_match #16" in "\n".join(matching_lines)
    assert mismatched_exit == 1
    assert (
        "FAIL branch_issue_match expected issue #17 but current branch is "
        "'codex/issue-016-demo-readiness'"
    ) in "\n".join(mismatched_lines)

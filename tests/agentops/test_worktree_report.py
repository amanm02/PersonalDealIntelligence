from pathlib import Path

from tools.agentops import worktree_report


def test_parse_worktree_list_reads_porcelain_records() -> None:
    output = """worktree /tmp/repo
HEAD abc123
branch refs/heads/main

worktree /tmp/repo-agent
HEAD def456
branch refs/heads/codex/issue-052-agentops
"""

    worktrees = worktree_report.parse_worktree_list(output)

    assert len(worktrees) == 2
    assert worktrees[0].path == Path("/tmp/repo")
    assert worktrees[0].branch == "main"
    assert worktrees[1].branch == "codex/issue-052-agentops"


def test_has_obvious_issue_mapping_accepts_issue_number_or_map_text() -> None:
    assert worktree_report.has_obvious_issue_mapping(
        "codex/issue-052-agentops", ""
    )
    assert worktree_report.has_obvious_issue_mapping(
        "codex/agentops-e-tools", "planned branch: codex/agentops-e-tools"
    )
    assert not worktree_report.has_obvious_issue_mapping(
        "codex/agentops-e-tools", ""
    )


def test_analyze_worktrees_flags_dirty_merged_and_unmapped(monkeypatch) -> None:
    worktrees = [
        worktree_report.Worktree(
            path=Path("/tmp/repo-agent"),
            head="abc123",
            branch_ref="refs/heads/codex/agentops-e-tools",
        )
    ]

    monkeypatch.setattr(worktree_report, "is_dirty", lambda path: True)
    monkeypatch.setattr(
        worktree_report, "is_likely_merged", lambda branch, base_ref: True
    )

    findings = worktree_report.analyze_worktrees(
        worktrees,
        issue_map_text="",
        base_ref="origin/main",
    )

    assert [finding.message for finding in findings] == [
        "dirty worktree has uncommitted changes",
        "branch tip is already an ancestor of origin/main",
        "branch has no obvious issue mapping",
    ]
    assert all(finding.level == "WARN" for finding in findings)


def test_analyze_worktrees_reports_ok_when_no_warnings(monkeypatch) -> None:
    worktrees = [
        worktree_report.Worktree(
            path=Path("/tmp/repo-agent"),
            head="abc123",
            branch_ref="refs/heads/codex/issue-052-agentops",
        )
    ]

    monkeypatch.setattr(worktree_report, "is_dirty", lambda path: False)
    monkeypatch.setattr(
        worktree_report, "is_likely_merged", lambda branch, base_ref: False
    )

    findings = worktree_report.analyze_worktrees(
        worktrees,
        issue_map_text="",
        base_ref="origin/main",
    )

    assert findings == [
        worktree_report.WorktreeFinding(
            level="OK",
            path=Path("/tmp/repo-agent"),
            branch="codex/issue-052-agentops",
            message="worktree has no hygiene warnings",
            action="none",
        )
    ]

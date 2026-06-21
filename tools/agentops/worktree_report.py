from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from tools.agentops.common import ROOT, main_check, rel


ISSUE_PATTERN = re.compile(r"(?:^|[-_/])(?:issue[-_/]?)?#?\d{1,5}(?:$|[-_/])")


@dataclass(frozen=True)
class Worktree:
    path: Path
    head: str | None
    branch_ref: str | None

    @property
    def branch(self) -> str | None:
        if self.branch_ref is None:
            return None
        if self.branch_ref.startswith("refs/heads/"):
            return self.branch_ref.removeprefix("refs/heads/")
        return self.branch_ref


@dataclass(frozen=True)
class WorktreeFinding:
    level: str
    path: Path
    branch: str
    message: str
    action: str


def run_git(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_worktree_list(output: str) -> list[Worktree]:
    worktrees: list[Worktree] = []
    current: dict[str, str] = {}

    def flush() -> None:
        if not current:
            return
        path = current.get("worktree")
        if path:
            worktrees.append(
                Worktree(
                    path=Path(path),
                    head=current.get("HEAD"),
                    branch_ref=current.get("branch"),
                )
            )
        current.clear()

    for line in output.splitlines():
        if not line:
            flush()
            continue
        key, _, value = line.partition(" ")
        if key == "worktree" and current:
            flush()
        current[key] = value
    flush()
    return worktrees


def load_issue_map(path: Path = ROOT / "docs/issue-map.md") -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").lower()


def has_obvious_issue_mapping(branch: str | None, issue_map_text: str) -> bool:
    if not branch:
        return False
    normalized = branch.lower()
    if ISSUE_PATTERN.search(normalized):
        return True
    return normalized in issue_map_text


def is_dirty(path: Path) -> bool:
    result = run_git(["status", "--porcelain"], cwd=path)
    return bool(result.stdout.strip())


def is_likely_merged(branch: str | None, base_ref: str) -> bool:
    if not branch:
        return False
    if branch in {"main", "origin/main", base_ref}:
        return False
    result = run_git(["merge-base", "--is-ancestor", branch, base_ref])
    return result.returncode == 0


def collect_worktrees() -> list[Worktree]:
    result = run_git(["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git worktree list failed")
    return parse_worktree_list(result.stdout)


def analyze_worktrees(
    worktrees: Iterable[Worktree],
    *,
    issue_map_text: str,
    base_ref: str = "origin/main",
) -> list[WorktreeFinding]:
    findings: list[WorktreeFinding] = []
    for worktree in worktrees:
        branch = worktree.branch or "(detached)"
        worktree_findings: list[WorktreeFinding] = []
        if is_dirty(worktree.path):
            worktree_findings.append(
                WorktreeFinding(
                    level="WARN",
                    path=worktree.path,
                    branch=branch,
                    message="dirty worktree has uncommitted changes",
                    action="inspect and commit, stash, or move the uncommitted work before cleanup",
                )
            )
        if is_likely_merged(worktree.branch, base_ref):
            worktree_findings.append(
                WorktreeFinding(
                    level="WARN",
                    path=worktree.path,
                    branch=branch,
                    message=f"branch tip is already an ancestor of {base_ref}",
                    action="cleanup candidate after confirming there is no unmerged user work",
                )
            )
        if not has_obvious_issue_mapping(worktree.branch, issue_map_text):
            worktree_findings.append(
                WorktreeFinding(
                    level="WARN",
                    path=worktree.path,
                    branch=branch,
                    message="branch has no obvious issue mapping",
                    action="rename branch or document the PR/issue mapping before assigning new work",
                )
            )
        if worktree_findings:
            findings.extend(worktree_findings)
        else:
            findings.append(
                WorktreeFinding(
                    level="OK",
                    path=worktree.path,
                    branch=branch,
                    message="worktree has no hygiene warnings",
                    action="none",
                )
            )
    return findings


def format_finding(finding: WorktreeFinding) -> str:
    path = rel(finding.path) if finding.path.is_relative_to(ROOT) else str(finding.path)
    return f"{finding.level} {path} [{finding.branch}] {finding.message}; action: {finding.action}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report advisory git worktree hygiene signals without deleting anything."
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Reference used to flag branch tips already merged into the base.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        worktrees = collect_worktrees()
    except RuntimeError as exc:
        print(f"FAIL {exc}")
        return main_check("worktree_report", [False])

    findings = analyze_worktrees(
        worktrees,
        issue_map_text=load_issue_map(),
        base_ref=args.base_ref,
    )
    for finding in findings:
        print(format_finding(finding))
    print("NOTE worktree_report is read-only and never deletes worktrees or branches")
    return main_check("worktree_report", [True])


if __name__ == "__main__":
    raise SystemExit(main())

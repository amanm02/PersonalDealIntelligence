from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tools.agentops.common import ROOT


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class WorkState:
    worktree_path: Path | None
    branch: str
    dirty_entries: tuple[str, ...]
    base_ref: str
    base_available: bool
    ahead: int | None
    behind: int | None
    git_errors: tuple[str, ...] = ()

    @property
    def dirty(self) -> bool:
        return bool(self.dirty_entries)

    @property
    def stale_suspected(self) -> bool:
        return self.behind is not None and self.behind > 0


def run_git(repo: Path, args: list[str]) -> GitResult:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
        text=True,
    )
    return GitResult(result.returncode, result.stdout.strip(), result.stderr.strip())


def _git_error(label: str, result: GitResult) -> str:
    detail = result.stderr or result.stdout or f"exit {result.returncode}"
    return f"{label}: {detail}"


def collect_work_state(repo: Path, base_ref: str = "origin/main") -> WorkState:
    errors: list[str] = []

    root_result = run_git(repo, ["rev-parse", "--show-toplevel"])
    worktree_path: Path | None = None
    if root_result.returncode == 0:
        worktree_path = Path(root_result.stdout)
    else:
        errors.append(_git_error("worktree", root_result))

    branch_result = run_git(repo, ["branch", "--show-current"])
    branch = branch_result.stdout if branch_result.returncode == 0 and branch_result.stdout else "DETACHED"
    if branch_result.returncode != 0:
        errors.append(_git_error("branch", branch_result))

    dirty_result = run_git(repo, ["status", "--short"])
    dirty_entries: tuple[str, ...] = ()
    if dirty_result.returncode == 0:
        dirty_entries = tuple(line for line in dirty_result.stdout.splitlines() if line)
    else:
        errors.append(_git_error("dirty tree", dirty_result))

    base_result = run_git(repo, ["rev-parse", "--verify", f"{base_ref}^{{commit}}"])
    base_available = base_result.returncode == 0
    ahead: int | None = None
    behind: int | None = None
    if base_available:
        divergence_result = run_git(repo, ["rev-list", "--left-right", "--count", f"{base_ref}...HEAD"])
        if divergence_result.returncode == 0:
            parts = divergence_result.stdout.split()
            if len(parts) == 2:
                behind = int(parts[0])
                ahead = int(parts[1])
            else:
                errors.append(f"divergence: unexpected output {divergence_result.stdout!r}")
        else:
            errors.append(_git_error("divergence", divergence_result))
    else:
        errors.append(_git_error(f"base ref {base_ref}", base_result))

    return WorkState(
        worktree_path=worktree_path,
        branch=branch,
        dirty_entries=dirty_entries,
        base_ref=base_ref,
        base_available=base_available,
        ahead=ahead,
        behind=behind,
        git_errors=tuple(errors),
    )


def branch_matches_issue(branch: str, issue_number: int) -> bool:
    normalized = branch.lower()
    expected = str(issue_number)
    padded = f"{issue_number:03d}"
    tokens = {
        f"issue-{expected}",
        f"issue_{expected}",
        f"issue/{expected}",
        f"#{expected}",
        f"-{expected}-",
        f"/{expected}-",
        f"issue-{padded}",
        f"issue_{padded}",
        f"issue/{padded}",
        f"#{padded}",
        f"-{padded}-",
        f"/{padded}-",
    }
    return any(token in normalized for token in tokens)


def render_work_state(state: WorkState, expected_issue: int | None = None) -> tuple[int, list[str]]:
    lines: list[str] = []
    status_ok = True

    if state.worktree_path is None:
        lines.append("FAIL worktree_path unknown")
        status_ok = False
    else:
        lines.append(f"INFO worktree_path {state.worktree_path}")

    lines.append(f"INFO current_branch {state.branch}")

    if expected_issue is not None:
        if branch_matches_issue(state.branch, expected_issue):
            lines.append(f"OK branch_issue_match #{expected_issue}")
        else:
            status_ok = False
            lines.append(
                f"FAIL branch_issue_match expected issue #{expected_issue} "
                f"but current branch is {state.branch!r}"
            )

    if state.dirty:
        status_ok = False
        lines.append(f"FAIL dirty_tree yes ({len(state.dirty_entries)} entries)")
        lines.extend(f"  {entry}" for entry in state.dirty_entries)
    else:
        lines.append("OK dirty_tree no")

    if not state.base_available:
        status_ok = False
        lines.append(f"FAIL divergence base_ref_missing {state.base_ref}")
    elif state.ahead is None or state.behind is None:
        status_ok = False
        lines.append(f"FAIL divergence unknown base={state.base_ref}")
    else:
        label = "WARN" if state.stale_suspected else "OK"
        if state.stale_suspected:
            status_ok = False
        lines.append(
            f"{label} divergence_from_{state.base_ref} "
            f"behind={state.behind} ahead={state.ahead}"
        )

    if state.stale_suspected:
        lines.append(
            f"WARN stale_branch_suspicion branch is {state.behind} commit(s) "
            f"behind {state.base_ref}"
        )
    elif state.base_available and state.behind == 0:
        lines.append("OK stale_branch_suspicion no")

    for error in state.git_errors:
        lines.append(f"DETAIL {error}")

    lines.append(f"check_work_state: {'PASS' if status_ok else 'FAIL'}")
    return (0 if status_ok else 1), lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report read-only git/worktree state for AgentOps hygiene.")
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository path to inspect.")
    parser.add_argument("--base", default="origin/main", help="Base ref used for divergence checks.")
    parser.add_argument(
        "--expected-issue",
        type=int,
        help="Fail if the current branch name does not obviously map to this issue number.",
    )
    parser.add_argument(
        "--advisory",
        action="store_true",
        help="Print the same findings but exit zero so hygiene reports can surface local state without blocking.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state = collect_work_state(args.repo, args.base)
    exit_code, lines = render_work_state(state, expected_issue=args.expected_issue)
    for line in lines:
        print(line)
    if args.advisory and exit_code != 0:
        print("check_work_state: ADVISORY_ONLY")
        return 0
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

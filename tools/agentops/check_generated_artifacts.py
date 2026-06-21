from __future__ import annotations

import subprocess
from pathlib import Path

from tools.agentops.common import ROOT, main_check


GENERATED_PATTERNS = (
    "__pycache__",
    ".pyc",
    ".pyo",
    ".pytest_cache",
)


def git_status(repo: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--short", "--untracked-files=all"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(detail)
    return [line for line in result.stdout.splitlines() if line.strip()]


def git_tracked_files(repo: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(detail)
    return [line for line in result.stdout.splitlines() if line.strip()]


def status_path(line: str) -> str:
    payload = line[3:] if len(line) > 3 else line
    if " -> " in payload:
        payload = payload.split(" -> ", 1)[1]
    return payload.strip()


def is_generated_path(path: str) -> bool:
    return any(pattern in path for pattern in GENERATED_PATTERNS)


def find_generated_status_entries(lines: list[str]) -> list[str]:
    return [line for line in lines if is_generated_path(status_path(line))]


def find_generated_tracked_files(paths: list[str]) -> list[str]:
    return [path for path in paths if is_generated_path(path)]


def validate_generated_artifacts(repo: Path = ROOT) -> bool:
    try:
        status_offenders = find_generated_status_entries(git_status(repo))
        tracked_offenders = find_generated_tracked_files(git_tracked_files(repo))
    except RuntimeError as exc:
        print(f"FAIL git artifact scan unavailable: {exc}")
        return False

    if not status_offenders and not tracked_offenders:
        print("OK no generated Python cache artifacts in git status or tracked files")
        return True

    for offender in status_offenders:
        print(f"FAIL generated artifact present: {offender}")
    for offender in tracked_offenders:
        print(f"FAIL generated artifact tracked: {offender}")
    print("Suggestion: remove cache artifacts before committing; do not track generated files.")
    return False


if __name__ == "__main__":
    raise SystemExit(main_check("check_generated_artifacts", [validate_generated_artifacts()]))

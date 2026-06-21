from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


REQUIRED_MARKERS = [
    "## Summary",
    "## Linked issue",
    "## Dependency status",
    "## Owned files",
    "## Blocked files",
    "## Concurrency risk",
    "## Validation",
    "Product CI status",
    "AgentOps CI status",
    "## Risks",
]


def _run_gh(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(["gh", *args], capture_output=True, check=False, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(detail)
    return json.loads(result.stdout)


def load_pr_body(repo: str, number: int) -> str:
    if shutil.which("gh") is None:
        raise RuntimeError("gh is not available on PATH")
    item = _run_gh(["pr", "view", str(number), "--repo", repo, "--json", "body"])
    return str(item.get("body") or "")


def validate_pr_body_text(text: str) -> bool:
    ok = True
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            print(f"FAIL PR body missing marker: {marker}")
            ok = False
        else:
            print(f"OK PR body marker: {marker}")
    return ok


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an actual PR body contains review metadata.")
    parser.add_argument("--body-file", type=Path, help="Local markdown file containing a PR body.")
    parser.add_argument("--github-pr", type=int, help="Read a PR body with gh.")
    parser.add_argument("--repo", default="amanm02/PersonalDealIntelligence", help="GitHub owner/repo.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if bool(args.body_file) == bool(args.github_pr):
        print("FAIL pass exactly one of --body-file or --github-pr")
        print("check_pr_body: FAIL")
        return 1

    try:
        if args.body_file:
            text = args.body_file.read_text(encoding="utf-8")
        else:
            text = load_pr_body(args.repo, int(args.github_pr))
    except (OSError, RuntimeError) as exc:
        print(f"FAIL PR body unavailable: {exc}")
        print("check_pr_body: FAIL")
        return 1

    ok = validate_pr_body_text(text)
    print(f"check_pr_body: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

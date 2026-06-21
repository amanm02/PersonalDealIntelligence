from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.agentops.common import ROOT


REQUIRED_SECTIONS = [
    "## Dependencies",
    "## Owned files",
    "## Blocked files",
    "## Validation commands",
    "## Stop conditions",
]

ISSUE_HYGIENE_DOC_MARKERS = [
    "## Standard Issue Contract",
    "## Copy-Paste Metadata Template",
    "## Dependencies",
    "## Owned files",
    "## Blocked files",
    "## Validation commands",
    "## Stop conditions",
]


@dataclass(frozen=True)
class IssueBody:
    number: int
    title: str
    body: str
    state: str = "OPEN"


def _run_gh(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(["gh", *args], capture_output=True, check=False, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(detail)
    return json.loads(result.stdout)


def load_fixture(path: Path) -> list[IssueBody]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("issues", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError("fixture must be a list or an object with an issues list")
    issues = []
    for item in items:
        issues.append(
            IssueBody(
                number=int(item["number"]),
                title=str(item.get("title") or ""),
                body=str(item.get("body") or ""),
                state=str(item.get("state") or "OPEN"),
            )
        )
    return issues


def load_github_issue(repo: str, number: int) -> list[IssueBody]:
    if shutil.which("gh") is None:
        raise RuntimeError("gh is not available on PATH")
    item = _run_gh(
        [
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,state",
        ]
    )
    return [
        IssueBody(
            number=int(item["number"]),
            title=str(item.get("title") or ""),
            body=str(item.get("body") or ""),
            state=str(item.get("state") or "OPEN"),
        )
    ]


def missing_sections(body: str) -> list[str]:
    return [section for section in REQUIRED_SECTIONS if section not in body]


def validate_issue_bodies(issues: list[IssueBody]) -> bool:
    ok = True
    for issue in issues:
        if issue.state.upper() == "CLOSED":
            print(f"OK #{issue.number} closed issue skipped")
            continue
        missing = missing_sections(issue.body)
        if missing:
            ok = False
            print(f"FAIL #{issue.number} {issue.title} missing sections: {', '.join(missing)}")
        else:
            print(f"OK #{issue.number} {issue.title} issue hygiene sections present")
    return ok


def validate_hygiene_doc(path: Path | None = None) -> bool:
    doc_path = path or ROOT / "docs/agentops/issue-hygiene.md"
    if not doc_path.exists():
        print("FAIL missing docs/agentops/issue-hygiene.md")
        return False
    text = doc_path.read_text(encoding="utf-8")
    ok = True
    for marker in ISSUE_HYGIENE_DOC_MARKERS:
        if marker not in text:
            print(f"FAIL issue hygiene doc missing marker: {marker}")
            ok = False
        else:
            print(f"OK issue hygiene doc marker: {marker}")
    return ok


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check issue-body hygiene metadata.")
    parser.add_argument("--fixture", type=Path, help="Offline gh issue JSON fixture.")
    parser.add_argument("--github-issue", type=int, help="Read a single issue with gh.")
    parser.add_argument("--repo", default="amanm02/PersonalDealIntelligence", help="GitHub owner/repo.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.fixture:
            ok = validate_issue_bodies(load_fixture(args.fixture))
        elif args.github_issue:
            ok = validate_issue_bodies(load_github_issue(args.repo, args.github_issue))
        else:
            ok = validate_hygiene_doc()
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"FAIL issue hygiene input unavailable: {exc}")
        print("check_issue_hygiene: FAIL")
        return 1

    print(f"check_issue_hygiene: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

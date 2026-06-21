from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.agentops.common import ROOT


ISSUE_ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*#(?P<number>\d+)\s*\|.*\|\s*(?P<status>[^|]+?)\s*\|\s*$")
CURRENT_WORK_RE = re.compile(
    r"^## .*(current[- ]work|active[- ]work|concurrency)",
    re.IGNORECASE | re.MULTILINE,
)
KNOWN_STATUSES = {"open", "closed", "in review"}
REQUIRED_ISSUES = [16, 17, *range(27, 44), 52]


@dataclass(frozen=True)
class IssueMapEntry:
    number: int
    status: str
    raw_status: str
    line_number: int


@dataclass(frozen=True)
class ComparisonResult:
    ok: bool
    lines: tuple[str, ...]


def normalize_status(value: str) -> str:
    normalized = value.strip().lower().replace("_", " ").replace("-", " ")
    if normalized.startswith("open"):
        return "open"
    if "in review" in normalized or "under review" in normalized:
        return "in review"
    if normalized in {"review", "in review", "under review"}:
        return "in review"
    if normalized in {"opened", "open"}:
        return "open"
    if normalized in {"closed", "merged", "done"} or normalized.startswith("closed;"):
        return "closed"
    return normalized


def parse_issue_map(path: Path) -> list[IssueMapEntry]:
    entries: list[IssueMapEntry] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = ISSUE_ROW_RE.match(line)
        if not match:
            continue
        raw_status = match.group("status").strip()
        status = normalize_status(raw_status)
        entries.append(
            IssueMapEntry(
                number=int(match.group("number")),
                status=status,
                raw_status=raw_status,
                line_number=line_number,
            )
        )
    return entries


def _status_from_fixture_item(item: Any) -> str:
    if isinstance(item, str):
        return normalize_status(item)
    if not isinstance(item, dict):
        raise ValueError(f"fixture item must be an object or status string, got {type(item).__name__}")

    if "status" in item:
        return normalize_status(str(item["status"]))

    if item.get("in_review") is True:
        return "in review"

    linked_pr_state = item.get("linked_pr_state") or item.get("pr_state")
    if linked_pr_state and normalize_status(str(linked_pr_state)) == "open":
        return "in review"

    if "state" not in item:
        raise ValueError("fixture item must include status, state, or in_review")
    return normalize_status(str(item["state"]))


def load_fixture_statuses(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    statuses: dict[int, str] = {}

    if isinstance(raw, dict) and "issues" in raw:
        raw_items = raw["issues"]
    else:
        raw_items = raw

    if isinstance(raw_items, dict):
        for key, value in raw_items.items():
            number = int(str(key).lstrip("#"))
            statuses[number] = _status_from_fixture_item(value)
        return statuses

    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict) or "number" not in item:
                raise ValueError("fixture issue list items must include number")
            statuses[int(item["number"])] = _status_from_fixture_item(item)
        return statuses

    raise ValueError("fixture must be a mapping, a list, or an object with an issues field")


def _run_gh(args: list[str]) -> list[dict[str, Any]]:
    result = subprocess.run(["gh", *args], capture_output=True, check=False, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(detail)
    return json.loads(result.stdout)


def load_github_statuses(repo: str, limit: int = 200) -> dict[int, str]:
    if shutil.which("gh") is None:
        raise RuntimeError("gh is not available on PATH")

    issues = _run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            str(limit),
            "--json",
            "number,state",
        ]
    )
    statuses = {int(issue["number"]): normalize_status(str(issue["state"])) for issue in issues}

    prs = _run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "number,closingIssuesReferences",
        ]
    )
    for pr in prs:
        for issue in pr.get("closingIssuesReferences", []) or []:
            number = issue.get("number")
            if number is not None and statuses.get(int(number)) == "open":
                statuses[int(number)] = "in review"

    return statuses


def load_github_pr_states(repo: str, limit: int = 200) -> dict[int, str]:
    if shutil.which("gh") is None:
        raise RuntimeError("gh is not available on PATH")

    prs = _run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            str(limit),
            "--json",
            "number,state",
        ]
    )
    return {int(pr["number"]): str(pr["state"]).strip().lower() for pr in prs}


def compare_issue_map(
    entries: list[IssueMapEntry],
    source_statuses: dict[int, str],
    source_pr_states: dict[int, str] | None = None,
) -> ComparisonResult:
    lines: list[str] = []
    ok = True
    seen: set[int] = set()
    source_pr_states = source_pr_states or {}

    for entry in entries:
        seen.add(entry.number)
        if entry.status not in KNOWN_STATUSES:
            ok = False
            lines.append(
                f"FAIL #{entry.number} issue-map has unknown status "
                f"{entry.status!r} on line {entry.line_number}"
            )
            continue

        source_status = source_statuses.get(entry.number)
        if source_status is None:
            ok = False
            lines.append(f"FAIL #{entry.number} missing from comparison source")
            continue

        source_status = normalize_status(source_status)
        if entry.status != source_status:
            ok = False
            lines.append(
                f"FAIL #{entry.number} stale status: issue-map has "
                f"{entry.status!r}, source has {source_status!r}"
            )
        else:
            lines.append(f"OK #{entry.number} status {entry.status}")

        for pr_number in re.findall(r"PR\s+#(\d+)\s+in\s+review", entry.raw_status, flags=re.IGNORECASE):
            pr_state = source_pr_states.get(int(pr_number))
            if pr_state and pr_state != "open":
                ok = False
                lines.append(
                    f"FAIL #{entry.number} stale PR annotation: issue-map says "
                    f"PR #{pr_number} in review, source has {pr_state!r}"
                )
            elif pr_state == "open":
                lines.append(f"OK #{entry.number} PR #{pr_number} annotation in review")

    for number in sorted(set(source_statuses) - seen):
        lines.append(f"WARN source includes #{number} not present in issue map")

    lines.append(f"check_issue_map_freshness: {'PASS' if ok else 'FAIL'}")
    return ComparisonResult(ok=ok, lines=tuple(lines))


def static_check(issue_map_path: Path, entries: list[IssueMapEntry]) -> ComparisonResult:
    text = issue_map_path.read_text(encoding="utf-8")
    lines: list[str] = []
    ok = True

    if CURRENT_WORK_RE.search(text):
        lines.append("OK issue map has current-work/concurrency scaffolding")
    else:
        ok = False
        lines.append("FAIL issue map missing current-work or concurrency section")

    for number in REQUIRED_ISSUES:
        if f"#{number}" in text:
            lines.append(f"OK issue map references #{number}")
        else:
            ok = False
            lines.append(f"FAIL issue map missing required reference #{number}")

    for entry in entries:
        if entry.status not in KNOWN_STATUSES:
            ok = False
            lines.append(
                f"FAIL #{entry.number} issue-map has unknown status "
                f"{entry.status!r} on line {entry.line_number}"
            )

    lines.append(f"check_issue_map_freshness: {'PASS' if ok else 'FAIL'}")
    return ComparisonResult(ok=ok, lines=tuple(lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare docs/issue-map.md statuses against static or GitHub data.")
    parser.add_argument("--issue-map", type=Path, default=ROOT / "docs/issue-map.md")
    parser.add_argument("--fixture", type=Path, help="Offline JSON fixture with issue statuses.")
    parser.add_argument("--github", action="store_true", help="Use gh to read live GitHub issue and PR state.")
    parser.add_argument("--repo", default="amanm02/PersonalDealIntelligence", help="GitHub owner/repo for --github.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum issues/PRs to read from gh.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    entries = parse_issue_map(args.issue_map)

    if args.fixture:
        source_label = f"fixture {args.fixture}"
        try:
            source_statuses = load_fixture_statuses(args.fixture)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"FAIL fixture status lookup unavailable: {exc}")
            print("check_issue_map_freshness: FAIL")
            return 1
    elif args.github:
        source_label = f"GitHub {args.repo}"
        try:
            source_statuses = load_github_statuses(args.repo, args.limit)
            source_pr_states = load_github_pr_states(args.repo, args.limit)
        except RuntimeError as exc:
            print(f"FAIL GitHub status lookup unavailable: {exc}")
            print("check_issue_map_freshness: FAIL")
            return 1
    else:
        print(f"INFO issue_map {args.issue_map}")
        print("INFO comparison_source static")
        result = static_check(args.issue_map, entries)
        for line in result.lines:
            print(line)
        return 0 if result.ok else 1

    print(f"INFO issue_map {args.issue_map}")
    print(f"INFO comparison_source {source_label}")
    result = compare_issue_map(entries, source_statuses, locals().get("source_pr_states"))
    for line in result.lines:
        print(line)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

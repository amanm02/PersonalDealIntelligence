from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CHAIN = "69,72,78,81,68,71,77,80,70,73,79,82,83,34,74,75"
ISSUE_TOKEN_RE = re.compile(r"\d+")


@dataclass(frozen=True)
class IssueSummary:
    number: int
    title: str
    state: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class PrSummary:
    number: int
    title: str
    state: str
    head: str
    base: str
    merged_at: str
    closes: tuple[int, ...]


def parse_chain(value: str) -> list[int]:
    numbers = [int(match.group(0)) for match in ISSUE_TOKEN_RE.finditer(value)]
    if not numbers:
        raise ValueError("chain must contain at least one issue number")
    return numbers


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _items(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        for key in ("issues", "prs", "items"):
            if isinstance(raw.get(key), list):
                return raw[key]
    if isinstance(raw, list):
        return raw
    raise ValueError("fixture must be a list or contain issues/prs/items")


def _labels(raw: Any) -> tuple[str, ...]:
    labels: list[str] = []
    for label in raw or []:
        if isinstance(label, str):
            labels.append(label)
        elif isinstance(label, dict):
            labels.append(str(label.get("name") or ""))
    return tuple(sorted(label for label in labels if label))


def load_issues(path: Path | None) -> dict[int, IssueSummary]:
    if path is None:
        return {}
    issues: dict[int, IssueSummary] = {}
    for item in _items(_read_json(path)):
        number = int(item["number"])
        issues[number] = IssueSummary(
            number=number,
            title=str(item.get("title") or ""),
            state=str(item.get("state") or "UNKNOWN").upper(),
            labels=_labels(item.get("labels")),
        )
    return issues


def _closing_numbers(item: dict[str, Any]) -> tuple[int, ...]:
    refs = item.get("closingIssuesReferences") or item.get("closes") or []
    numbers: list[int] = []
    for ref in refs:
        if isinstance(ref, int):
            numbers.append(ref)
        elif isinstance(ref, dict) and ref.get("number") is not None:
            numbers.append(int(ref["number"]))
    return tuple(sorted(set(numbers)))


def load_prs(path: Path | None) -> list[PrSummary]:
    if path is None:
        return []
    prs: list[PrSummary] = []
    for item in _items(_read_json(path)):
        prs.append(
            PrSummary(
                number=int(item["number"]),
                title=str(item.get("title") or ""),
                state=str(item.get("state") or "UNKNOWN").upper(),
                head=str(item.get("headRefName") or item.get("head") or ""),
                base=str(item.get("baseRefName") or item.get("base") or ""),
                merged_at=str(item.get("mergedAt") or ""),
                closes=_closing_numbers(item),
            )
        )
    return prs


def _run_gh(args: list[str]) -> Any:
    result = subprocess.run(["gh", *args], capture_output=True, check=False, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(detail)
    return json.loads(result.stdout)


def load_github(repo: str, limit: int) -> tuple[dict[int, IssueSummary], list[PrSummary]]:
    if shutil.which("gh") is None:
        raise RuntimeError("gh is not available on PATH")
    raw_issues = _run_gh(
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
            "number,title,state,labels",
        ]
    )
    raw_prs = _run_gh(
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
            "number,title,state,headRefName,baseRefName,mergedAt,closingIssuesReferences",
        ]
    )
    issue_path = Path("/tmp/pdi-agentops-chain-issues.json")
    pr_path = Path("/tmp/pdi-agentops-chain-prs.json")
    issue_path.write_text(json.dumps(raw_issues), encoding="utf-8")
    pr_path.write_text(json.dumps(raw_prs), encoding="utf-8")
    return load_issues(issue_path), load_prs(pr_path)


def issue_slug(number: int) -> str:
    return f"issue-{number:03d}"


def matching_prs(issue_number: int, prs: list[PrSummary]) -> list[PrSummary]:
    slug = issue_slug(issue_number)
    loose_slug = f"issue-{issue_number}"
    return [
        pr
        for pr in prs
        if issue_number in pr.closes or slug in pr.head or loose_slug in pr.head
    ]


def render_chain(chain: list[int], issues: dict[int, IssueSummary], prs: list[PrSummary]) -> tuple[bool, list[str]]:
    lines = ["Issue | State | Matching PRs | Notes", "--- | --- | --- | ---"]
    ok = True
    for number in chain:
        issue = issues.get(number)
        issue_state = issue.state if issue else "UNKNOWN"
        prs_for_issue = matching_prs(number, prs)
        pr_bits = [
            f"#{pr.number} {pr.state.lower()} {pr.head}->{pr.base}".strip()
            for pr in prs_for_issue
        ]
        notes: list[str] = []
        if issue is None:
            notes.append("issue not in source")
        elif issue.state == "OPEN" and any(pr.state == "MERGED" for pr in prs_for_issue):
            ok = False
            notes.append("merged PR but issue still open")
        if prs_for_issue and not any(number in pr.closes for pr in prs_for_issue):
            notes.append("matching PR lacks closure reference")
        if sum(1 for pr in prs_for_issue if pr.state == "OPEN") > 1:
            ok = False
            notes.append("multiple open PRs for issue")
        if not prs_for_issue:
            notes.append("no matching PR")
        lines.append(
            f"#{number} | {issue_state.lower()} | "
            f"{', '.join(pr_bits) if pr_bits else '-'} | {', '.join(notes) if notes else '-'}"
        )
    open_chain_prs = [
        pr
        for pr in prs
        if pr.state == "OPEN"
        and any(issue_slug(number) in pr.head or f"issue-{number}" in pr.head for number in chain)
    ]
    if open_chain_prs:
        lines.append("")
        lines.append("Open chain PRs:")
        for pr in open_chain_prs:
            lines.append(f"- #{pr.number} {pr.head} -> {pr.base}: {pr.title}")
    return ok, lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize a sequential issue chain from offline fixtures.")
    parser.add_argument("--chain", default=DEFAULT_CHAIN, help="Issue numbers, comma/space/arrow separated.")
    parser.add_argument("--issues-json", type=Path, help="Offline gh issue list/view JSON.")
    parser.add_argument("--prs-json", type=Path, help="Offline gh pr list/view JSON.")
    parser.add_argument("--github", action="store_true", help="Read live GitHub state with gh.")
    parser.add_argument("--repo", default="amanm02/PersonalDealIntelligence", help="GitHub owner/repo.")
    parser.add_argument("--limit", type=int, default=150, help="Live GitHub issue/PR list limit.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on detected closeout/conflict gaps.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        chain = parse_chain(args.chain)
        if args.github:
            issues, prs = load_github(args.repo, args.limit)
        else:
            issues = load_issues(args.issues_json)
            prs = load_prs(args.prs_json)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"FAIL chain status input unavailable: {exc}")
        print("chain_status: FAIL")
        return 1

    ok, lines = render_chain(chain, issues, prs)
    for line in lines:
        print(line)
    print(f"chain_status: {'PASS' if ok else 'WARN'}")
    return 1 if args.strict and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())

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


ISSUE_ROW_RE = re.compile(
    r"^\|\s*(?P<order>\d+)\s*\|\s*#(?P<number>\d+)\s*\|\s*(?P<title>[^|]+?)\s*\|"
    r"\s*(?P<depends>[^|]+?)\s*\|\s*(?P<status>[^|]+?)\s*\|\s*$"
)
ISSUE_REF_RE = re.compile(r"#(\d+)")


@dataclass(frozen=True)
class IssueMapRow:
    order: int
    number: int
    title: str
    depends_on: tuple[int, ...]
    status: str


@dataclass(frozen=True)
class IssueState:
    number: int
    title: str
    state: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class Recommendation:
    issue: IssueState
    score: int
    reasons: tuple[str, ...]
    risks: tuple[str, ...]


def normalize_status(value: str) -> str:
    value = value.strip().lower().replace("_", " ").replace("-", " ")
    if value.startswith("closed") or value in {"done", "merged"}:
        return "closed"
    if value.startswith("open"):
        return "open"
    if "review" in value:
        return "in review"
    return value


def parse_issue_map(path: Path) -> dict[int, IssueMapRow]:
    rows: dict[int, IssueMapRow] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ISSUE_ROW_RE.match(line)
        if not match:
            continue
        number = int(match.group("number"))
        rows[number] = IssueMapRow(
            order=int(match.group("order")),
            number=number,
            title=match.group("title").strip(),
            depends_on=tuple(int(value) for value in ISSUE_REF_RE.findall(match.group("depends"))),
            status=normalize_status(match.group("status")),
        )
    return rows


def _label_names(raw_labels: Any) -> tuple[str, ...]:
    labels: list[str] = []
    for label in raw_labels or []:
        if isinstance(label, str):
            labels.append(label)
        elif isinstance(label, dict) and "name" in label:
            labels.append(str(label["name"]))
    return tuple(sorted(label.strip().lower() for label in labels if label))


def _issue_from_item(item: dict[str, Any]) -> IssueState:
    return IssueState(
        number=int(item["number"]),
        title=str(item.get("title") or ""),
        state=str(item.get("state") or "OPEN").lower(),
        labels=_label_names(item.get("labels")),
    )


def load_fixture(path: Path) -> dict[int, IssueState]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("issues", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError("fixture must be a list or an object with an issues list")
    issues = [_issue_from_item(item) for item in items]
    return {issue.number: issue for issue in issues}


def _run_gh(args: list[str]) -> list[dict[str, Any]]:
    result = subprocess.run(["gh", *args], capture_output=True, check=False, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(detail)
    return json.loads(result.stdout)


def load_github_issues(repo: str, limit: int) -> dict[int, IssueState]:
    if shutil.which("gh") is None:
        raise RuntimeError("gh is not available on PATH")
    items = _run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "number,title,state,labels",
        ]
    )
    issues = [_issue_from_item(item) for item in items]
    return {issue.number: issue for issue in issues}


def _fallback_issues(rows: dict[int, IssueMapRow]) -> dict[int, IssueState]:
    issues: dict[int, IssueState] = {}
    for row in rows.values():
        if row.status == "open":
            issues[row.number] = IssueState(
                number=row.number,
                title=row.title,
                state="open",
                labels=(),
            )
    return issues


def unresolved_dependencies(row: IssueMapRow | None, rows: dict[int, IssueMapRow]) -> tuple[int, ...]:
    if row is None:
        return ()
    unresolved: list[int] = []
    for dependency in row.depends_on:
        dependency_row = rows.get(dependency)
        if dependency_row is None or dependency_row.status != "closed":
            unresolved.append(dependency)
    return tuple(unresolved)


def score_issue(
    issue: IssueState,
    rows: dict[int, IssueMapRow],
    *,
    include_blocked: bool = False,
) -> Recommendation | None:
    labels = set(issue.labels)
    row = rows.get(issue.number)
    reasons: list[str] = []
    risks: list[str] = []

    if issue.state != "open":
        return None

    blockers = unresolved_dependencies(row, rows)
    if blockers:
        risks.append("unresolved dependencies: " + ", ".join(f"#{number}" for number in blockers))

    if "blocked" in labels:
        risks.append("blocked label")
    if "needs-rewrite" in labels:
        risks.append("needs-rewrite label")

    hard_blocked = bool(blockers) or "blocked" in labels or "needs-rewrite" in labels
    if hard_blocked and not include_blocked:
        return None

    score = 0
    if row is not None:
        score += max(0, 80 - row.order)
        reasons.append(f"issue-map order {row.order}")
    else:
        risks.append("not present in issue map")

    if "codex-ready" in labels:
        score += 60
        reasons.append("codex-ready")
    if "phase:demo-critical" in labels:
        score += 30
        reasons.append("demo-critical")
    if "phase:mvp-core" in labels:
        score += 20
        reasons.append("mvp-core")
    if "track:quality" in labels:
        score += 10
        reasons.append("quality track")
    if "phase:post-mvp" in labels:
        score -= 30
        risks.append("post-mvp label")
    if "concurrency:exclusive" in labels:
        score -= 5
        risks.append("exclusive concurrency")
    if blockers:
        score -= 80
    if "blocked" in labels:
        score -= 80
    if "needs-rewrite" in labels:
        score -= 60

    if not reasons:
        reasons.append("open issue with no hard blockers")

    return Recommendation(issue=issue, score=score, reasons=tuple(reasons), risks=tuple(risks))


def recommend(
    issues: dict[int, IssueState],
    rows: dict[int, IssueMapRow],
    *,
    limit: int,
    include_blocked: bool = False,
) -> list[Recommendation]:
    recommendations = [
        recommendation
        for issue in issues.values()
        if (recommendation := score_issue(issue, rows, include_blocked=include_blocked)) is not None
    ]
    return sorted(
        recommendations,
        key=lambda item: (-item.score, rows.get(item.issue.number, IssueMapRow(9999, 0, "", (), "")).order, item.issue.number),
    )[:limit]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recommend the next safe GitHub issue to implement.")
    parser.add_argument("--issue-map", type=Path, default=ROOT / "docs/issue-map.md")
    parser.add_argument("--fixture", type=Path, help="Offline gh issue-list style JSON fixture.")
    parser.add_argument("--github", action="store_true", help="Use gh to read live open issues.")
    parser.add_argument("--repo", default="amanm02/PersonalDealIntelligence", help="GitHub owner/repo for --github.")
    parser.add_argument("--limit", type=int, default=3, help="Number of recommendations to print.")
    parser.add_argument("--issue-limit", type=int, default=200, help="Maximum issues to read from GitHub.")
    parser.add_argument(
        "--include-blocked",
        action="store_true",
        help="Include blocked or needs-rewrite issues as low-score candidates.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = parse_issue_map(args.issue_map)

    try:
        if args.fixture:
            source = f"fixture {args.fixture}"
            issues = load_fixture(args.fixture)
        elif args.github:
            source = f"GitHub {args.repo}"
            issues = load_github_issues(args.repo, args.issue_limit)
        else:
            source = f"static {args.issue_map}"
            issues = _fallback_issues(rows)
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"FAIL issue source unavailable: {exc}")
        print("recommend_next_issue: FAIL")
        return 1

    print(f"INFO issue_source {source}")
    recommendations = recommend(
        issues,
        rows,
        limit=args.limit,
        include_blocked=args.include_blocked,
    )

    if not recommendations:
        print("WARN no implementation-ready issue found")
        print("recommend_next_issue: PASS")
        return 0

    for index, item in enumerate(recommendations, start=1):
        print(f"{index}. #{item.issue.number} score={item.score} {item.issue.title}")
        print(f"   reasons: {', '.join(item.reasons)}")
        if item.risks:
            print(f"   risks: {', '.join(item.risks)}")

    print("recommend_next_issue: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

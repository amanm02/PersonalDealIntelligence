from __future__ import annotations

import json
from pathlib import Path

from tools.agentops.check_issue_map_freshness import (
    compare_issue_map,
    load_fixture_statuses,
    parse_issue_map,
    static_check,
)


def write_issue_map(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Issue Map",
                "",
                "| Order | Issue | Title | Depends on | Status |",
                "|---:|---|---|---|---|",
                "| 01 | #1 | Bootstrap | none | closed |",
                "| 02 | #2 | Add search | #1 | in review |",
                "| 03 | #3 | Next item | #2 | open |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_issue_map_freshness_passes_against_offline_fixture(tmp_path: Path) -> None:
    issue_map = tmp_path / "issue-map.md"
    fixture = tmp_path / "issues.json"
    write_issue_map(issue_map)
    fixture.write_text(
        json.dumps(
            {
                "issues": [
                    {"number": 1, "state": "closed"},
                    {"number": 2, "state": "open", "linked_pr_state": "open"},
                    {"number": 3, "status": "open"},
                ]
            }
        ),
        encoding="utf-8",
    )

    entries = parse_issue_map(issue_map)
    statuses = load_fixture_statuses(fixture)
    result = compare_issue_map(entries, statuses)

    assert result.ok is True
    assert "OK #1 status closed" in result.lines
    assert "OK #2 status in review" in result.lines
    assert "OK #3 status open" in result.lines
    assert result.lines[-1] == "check_issue_map_freshness: PASS"


def test_issue_map_freshness_reports_stale_status_and_missing_source(tmp_path: Path) -> None:
    issue_map = tmp_path / "issue-map.md"
    fixture = tmp_path / "issues.json"
    write_issue_map(issue_map)
    fixture.write_text(
        json.dumps(
            {
                "#1": "closed",
                "#2": {"state": "closed"},
                "#99": "open",
            }
        ),
        encoding="utf-8",
    )

    entries = parse_issue_map(issue_map)
    statuses = load_fixture_statuses(fixture)
    result = compare_issue_map(entries, statuses)

    assert result.ok is False
    assert "FAIL #2 stale status: issue-map has 'in review', source has 'closed'" in result.lines
    assert "FAIL #3 missing from comparison source" in result.lines
    assert "WARN source includes #99 not present in issue map" in result.lines
    assert result.lines[-1] == "check_issue_map_freshness: FAIL"


def test_issue_map_freshness_reports_stale_pr_annotation(tmp_path: Path) -> None:
    issue_map = tmp_path / "issue-map.md"
    issue_map.write_text(
        "\n".join(
            [
                "# Issue Map",
                "",
                "| Order | Issue | Title | Depends on | Status |",
                "|---:|---|---|---|---|",
                "| 14 | #16 | Demo readiness | #15 | open; PR #54 in review |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = compare_issue_map(
        parse_issue_map(issue_map),
        {16: "open"},
        {54: "merged"},
    )

    assert result.ok is False
    assert (
        "FAIL #16 stale PR annotation: issue-map says PR #54 in review, "
        "source has 'merged'"
    ) in result.lines


def test_issue_map_static_check_requires_current_work_and_issue_references(tmp_path: Path) -> None:
    issue_map = tmp_path / "issue-map.md"
    issue_map.write_text(
        "\n".join(
            [
                "# Issue Map",
                "",
                "## Current work and concurrency",
                "",
                "| Order | Issue | Title | Depends on | Status |",
                "|---:|---|---|---|---|",
                "| 14 | #16 | Demo readiness | #15 | open; PR #54 in review |",
                "| 15 | #17 | Public pilot | #16 | open |",
                *[
                    f"| {number} | #{number} | Placeholder | none | open |"
                    for number in range(27, 44)
                ],
                "| 52 | #52 | AgentOps hygiene | none | open |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = static_check(issue_map, parse_issue_map(issue_map))

    assert result.ok is True
    assert "OK issue map has current-work/concurrency scaffolding" in result.lines
    assert "OK issue map references #52" in result.lines

from __future__ import annotations

import json
from pathlib import Path

from tools.agentops.recommend_next_issue import (
    load_fixture,
    parse_issue_map,
    recommend,
    unresolved_dependencies,
)


def write_issue_map(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Issue Map",
                "",
                "| Order | Issue | Title | Depends on | Status |",
                "|---:|---|---|---|---|",
                "| 02 | #2 | Storage | #1 | closed |",
                "| 13 | #15 | Search | #14 | closed |",
                "| 14 | #16 | Demo readiness | #15 | open |",
                "| 15 | #17 | Public pilot | #16 | open |",
                "| 17 | #27 | Credit-card scope | #1 | closed |",
                "| 26 | #36 | Taxonomy | #2, #27 | open |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_recommender_skips_blocked_and_needs_rewrite_by_default(tmp_path: Path) -> None:
    issue_map = tmp_path / "issue-map.md"
    fixture = tmp_path / "issues.json"
    write_issue_map(issue_map)
    fixture.write_text(
        json.dumps(
            [
                {
                    "number": 16,
                    "title": "Demo readiness",
                    "state": "OPEN",
                    "labels": [{"name": "blocked"}, {"name": "codex-ready"}],
                },
                {
                    "number": 36,
                    "title": "Taxonomy",
                    "state": "OPEN",
                    "labels": [{"name": "phase:mvp-core"}],
                },
                {
                    "number": 40,
                    "title": "Credit card model",
                    "state": "OPEN",
                    "labels": [{"name": "needs-rewrite"}],
                },
            ]
        ),
        encoding="utf-8",
    )

    rows = parse_issue_map(issue_map)
    issues = load_fixture(fixture)
    results = recommend(issues, rows, limit=3)

    assert [item.issue.number for item in results] == [36]
    assert "mvp-core" in results[0].reasons


def test_recommender_can_include_blocked_with_risk_labels(tmp_path: Path) -> None:
    issue_map = tmp_path / "issue-map.md"
    fixture = tmp_path / "issues.json"
    write_issue_map(issue_map)
    fixture.write_text(
        json.dumps(
            [
                {
                    "number": 16,
                    "title": "Demo readiness",
                    "state": "OPEN",
                    "labels": [{"name": "blocked"}, {"name": "codex-ready"}],
                },
                {
                    "number": 17,
                    "title": "Public pilot",
                    "state": "OPEN",
                    "labels": [{"name": "phase:post-mvp"}],
                },
            ]
        ),
        encoding="utf-8",
    )

    rows = parse_issue_map(issue_map)
    issues = load_fixture(fixture)
    results = recommend(issues, rows, limit=3, include_blocked=True)

    assert [item.issue.number for item in results] == [16, 17]
    assert "blocked label" in results[0].risks
    assert "unresolved dependencies: #16" in results[1].risks


def test_unresolved_dependencies_detects_open_dependencies(tmp_path: Path) -> None:
    issue_map = tmp_path / "issue-map.md"
    write_issue_map(issue_map)

    rows = parse_issue_map(issue_map)

    assert unresolved_dependencies(rows[17], rows) == (16,)
    assert unresolved_dependencies(rows[16], rows) == ()

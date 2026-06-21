from __future__ import annotations

from pathlib import Path

from tools.agentops import check_pr_template


def test_current_pr_template_has_required_markers() -> None:
    template = Path(".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")

    assert check_pr_template.missing_markers(template) == []


def test_missing_required_marker_is_reported() -> None:
    template = "\n".join(
        marker
        for marker in check_pr_template.REQUIRED_MARKERS
        if marker != "## Concurrency risk"
    )

    assert check_pr_template.missing_markers(template) == ["## Concurrency risk"]

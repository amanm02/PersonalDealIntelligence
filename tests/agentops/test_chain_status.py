from __future__ import annotations

from tools.agentops.chain_status import IssueSummary, PrSummary, parse_chain, render_chain


def test_parse_chain_accepts_arrow_text() -> None:
    assert parse_chain("#69 -> #72 -> #80") == [69, 72, 80]


def test_render_chain_warns_when_merged_pr_left_issue_open() -> None:
    issues = {
        80: IssueSummary(number=80, title="Run history", state="OPEN", labels=()),
    }
    prs = [
        PrSummary(
            number=123,
            title="Implement #80",
            state="MERGED",
            head="codex/issue-080-score-run-history",
            base="main",
            merged_at="2026-06-22T02:51:04Z",
            closes=(),
        )
    ]

    ok, lines = render_chain([80], issues, prs)

    assert ok is False
    text = "\n".join(lines)
    assert "merged PR but issue still open" in text
    assert "matching PR lacks closure reference" in text


def test_render_chain_accepts_closed_issue_with_closing_pr() -> None:
    issues = {
        75: IssueSummary(number=75, title="Thresholds", state="CLOSED", labels=()),
    }
    prs = [
        PrSummary(
            number=131,
            title="Implement #75",
            state="MERGED",
            head="codex/issue-075-qa-thresholds",
            base="main",
            merged_at="2026-06-22T05:36:33Z",
            closes=(75,),
        )
    ]

    ok, lines = render_chain([75], issues, prs)

    assert ok is True
    assert "lacks closure" not in "\n".join(lines)

from __future__ import annotations

from tools.agentops.check_pr_body import CHAIN_REQUIRED_MARKERS, validate_pr_body_text


COMPLETE_BODY = """
## Summary

## Linked issue

## Dependency status

## Owned files

## Blocked files

## Concurrency risk

## Validation

## Product CI status

## AgentOps CI status

## Risks
"""


def test_pr_body_accepts_required_markers() -> None:
    assert validate_pr_body_text(COMPLETE_BODY) is True


def test_pr_body_rejects_missing_markers() -> None:
    assert validate_pr_body_text("## Summary\n") is False


def test_chain_pr_body_requires_compact_markers_and_closure() -> None:
    body = """
## Summary

Closes #75

## Files changed

## Validation

## Product safety

## Follow-ups
"""

    assert validate_pr_body_text(body, markers=CHAIN_REQUIRED_MARKERS, require_closure=True) is True


def test_chain_pr_body_accepts_issue_placeholder_closure() -> None:
    body = """
## Summary

Closes #<ISSUE_NUMBER>

## Files changed

## Validation

## Product safety

## Follow-ups
"""

    assert validate_pr_body_text(body, markers=CHAIN_REQUIRED_MARKERS, require_closure=True) is True


def test_chain_pr_body_rejects_missing_closure() -> None:
    body = """
## Summary

## Files changed

## Validation

## Product safety

## Follow-ups
"""

    assert validate_pr_body_text(body, markers=CHAIN_REQUIRED_MARKERS, require_closure=True) is False

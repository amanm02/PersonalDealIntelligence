from __future__ import annotations

from tools.agentops.check_pr_body import validate_pr_body_text


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

from __future__ import annotations

import json
from pathlib import Path

from tools.agentops.check_issue_hygiene import (
    load_fixture,
    missing_sections,
    validate_hygiene_doc,
    validate_issue_bodies,
)


COMPLETE_BODY = """
## Dependencies
- none

## Owned files
- docs/example.md

## Blocked files
- src/pdi/

## Validation commands
- git diff --check

## Stop conditions
- Stop if dependencies are stale.
"""


def test_issue_hygiene_accepts_complete_fixture(tmp_path: Path) -> None:
    fixture = tmp_path / "issues.json"
    fixture.write_text(
        json.dumps(
            [
                {"number": 1, "title": "Complete", "state": "OPEN", "body": COMPLETE_BODY},
                {"number": 2, "title": "Closed", "state": "CLOSED", "body": ""},
            ]
        ),
        encoding="utf-8",
    )

    assert validate_issue_bodies(load_fixture(fixture)) is True


def test_issue_hygiene_reports_missing_sections() -> None:
    assert missing_sections("## Dependencies\n") == [
        "## Owned files",
        "## Blocked files",
        "## Validation commands",
        "## Stop conditions",
    ]


def test_issue_hygiene_doc_contract(tmp_path: Path) -> None:
    doc = tmp_path / "issue-hygiene.md"
    doc.write_text(
        "\n".join(
            [
                "# Issue Hygiene",
                "## Standard Issue Contract",
                "## Copy-Paste Metadata Template",
                "## Dependencies",
                "## Owned files",
                "## Blocked files",
                "## Validation commands",
                "## Stop conditions",
            ]
        ),
        encoding="utf-8",
    )

    assert validate_hygiene_doc(doc) is True

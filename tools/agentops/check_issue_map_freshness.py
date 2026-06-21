from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ISSUE_MAP = ROOT / "docs" / "issue-map.md"
REQUIRED_ISSUES = [16, 17, *range(27, 44), 52]
SECTION_RE = re.compile(
    r"^## .*(current[- ]work|active[- ]work|concurrency)",
    re.IGNORECASE | re.MULTILINE,
)


def main() -> int:
    if not ISSUE_MAP.exists():
        print("FAIL missing docs/issue-map.md")
        return 1

    text = ISSUE_MAP.read_text(encoding="utf-8")
    failures: list[str] = []

    if not SECTION_RE.search(text):
        failures.append(
            "docs/issue-map.md needs a current-work, active-work, or "
            "concurrency section so agents can spot stale planning context."
        )

    for issue in REQUIRED_ISSUES:
        if f"#{issue}" not in text:
            failures.append(
                f"docs/issue-map.md missing reference to #{issue}; "
                "keep active roadmap issues visible or document a replacement structure."
            )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print("check_issue_map_freshness: FAIL")
        return 1

    print(
        "OK docs/issue-map.md has current-work/concurrency scaffolding "
        "and references required active roadmap issues"
    )
    print("check_issue_map_freshness: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

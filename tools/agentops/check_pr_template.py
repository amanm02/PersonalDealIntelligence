from __future__ import annotations

from pathlib import Path

from tools.agentops.common import ROOT, main_check

TEMPLATE_PATH = ".github/PULL_REQUEST_TEMPLATE.md"

REQUIRED_MARKERS = [
    "## Summary",
    "## Linked issue",
    "Closes #",
    "## Dependency status",
    "Depends on issue/PR:",
    "Must merge before issue/PR:",
    "## Owned files",
    "Files intentionally changed by this PR:",
    "## Blocked files",
    "Files intentionally avoided because another agent/PR owns them:",
    "## Concurrency risk",
    "overlap details and reviewer guidance:",
    "## Merge gate",
    "Ready to review",
    "Needs remediation",
    "Blocked by dependency",
    "Blocked by conflict",
    "Safe to merge after checks pass",
    "## Files changed",
    "## Validation commands and exact results",
    "Paste each command run and its exact result.",
    "git status --short",
    "git diff --stat",
    "git diff --check",
    "### Product CI status",
    "### AgentOps CI status",
    "## Runner / infrastructure caveats",
    "Self-hosted runner/toolcache/network caveat:",
    "## Risks / follow-ups",
]


def missing_markers(text: str) -> list[str]:
    return [marker for marker in REQUIRED_MARKERS if marker not in text]


def validate_template_text(text: str) -> bool:
    missing = missing_markers(text)
    if missing:
        for marker in missing:
            print(f"FAIL missing marker: {marker}")
        return False
    print(f"OK {TEMPLATE_PATH} required markers present")
    return True


def validate_template(path: Path | None = None) -> bool:
    template_path = path or ROOT / TEMPLATE_PATH
    if not template_path.exists():
        print(f"FAIL missing {TEMPLATE_PATH}")
        return False
    return validate_template_text(template_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main_check("check_pr_template", [validate_template()]))

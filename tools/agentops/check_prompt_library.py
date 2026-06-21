from __future__ import annotations

from pathlib import Path

from tools.agentops.common import ROOT, main_check


PROMPT_LIBRARY = "docs/prompt-library.md"

REQUIRED_PROMPTS = [
    "## Prompt: implement a GitHub issue",
    "## Prompt: current-state preflight",
    "## Prompt: Verification-only review",
    "## Prompt: issue audit/rewrite",
    "## Prompt: Next-issue selection",
    "## Prompt: Concurrency planning",
    "## Prompt: CI failure triage",
    "## Prompt: worktree/branch hygiene review",
]

IMPLEMENTATION_PROMPT_MARKERS = [
    "Run `python3 -m tools.agentops.check_work_state --advisory`",
    "Confirm issue state, dependencies, owned files, and blocked files",
    "Stop if the issue is closed, blocked, needs rewrite",
]


def _section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    next_heading = text.find("\n## Prompt:", start + len(heading))
    if next_heading == -1:
        return text[start:]
    return text[start:next_heading]


def validate_prompt_library(path: Path | None = None) -> bool:
    prompt_path = path or ROOT / PROMPT_LIBRARY
    if not prompt_path.exists():
        print(f"FAIL missing {PROMPT_LIBRARY}")
        return False

    text = prompt_path.read_text(encoding="utf-8")
    ok = True
    for marker in REQUIRED_PROMPTS:
        if marker not in text:
            print(f"FAIL missing prompt: {marker}")
            ok = False
        else:
            print(f"OK prompt present: {marker}")

    implementation_prompt = _section(text, "## Prompt: implement a GitHub issue")
    for marker in IMPLEMENTATION_PROMPT_MARKERS:
        if marker not in implementation_prompt:
            print(f"FAIL implementation prompt missing marker: {marker}")
            ok = False
        else:
            print(f"OK implementation prompt marker: {marker}")

    return ok


if __name__ == "__main__":
    raise SystemExit(main_check("check_prompt_library", [validate_prompt_library()]))

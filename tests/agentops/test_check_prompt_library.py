from __future__ import annotations

from pathlib import Path

from tools.agentops.check_prompt_library import validate_prompt_library


def test_prompt_library_requires_workflow_prompts_and_implementation_preflight(tmp_path: Path) -> None:
    prompt_library = tmp_path / "prompt-library.md"
    prompt_library.write_text(
        "\n".join(
            [
                "# Prompt Library",
                "",
                "## Prompt: implement a GitHub issue",
                "Run `python3 -m tools.agentops.check_work_state --advisory` before editing.",
                "Confirm issue state, dependencies, owned files, and blocked files.",
                "Stop if the issue is closed, blocked, needs rewrite, or already covered by a PR.",
                "",
                "## Prompt: current-state preflight",
                "body",
                "## Prompt: Verification-only review",
                "body",
                "## Prompt: issue audit/rewrite",
                "body",
                "## Prompt: Next-issue selection",
                "body",
                "## Prompt: Concurrency planning",
                "body",
                "## Prompt: CI failure triage",
                "body",
                "## Prompt: worktree/branch hygiene review",
                "body",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert validate_prompt_library(prompt_library) is True


def test_prompt_library_rejects_missing_implementation_preflight(tmp_path: Path) -> None:
    prompt_library = tmp_path / "prompt-library.md"
    prompt_library.write_text(
        "\n".join(
            [
                "# Prompt Library",
                "",
                "## Prompt: implement a GitHub issue",
                "Implement the issue.",
                "",
                "## Prompt: current-state preflight",
                "body",
                "## Prompt: Verification-only review",
                "body",
                "## Prompt: issue audit/rewrite",
                "body",
                "## Prompt: Next-issue selection",
                "body",
                "## Prompt: Concurrency planning",
                "body",
                "## Prompt: CI failure triage",
                "body",
                "## Prompt: worktree/branch hygiene review",
                "body",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert validate_prompt_library(prompt_library) is False

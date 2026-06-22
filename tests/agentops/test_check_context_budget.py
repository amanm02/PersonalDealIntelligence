from __future__ import annotations

from pathlib import Path

from tools.agentops.check_context_budget import main


def test_context_budget_single_file_mode_warns_but_passes(tmp_path: Path, capsys) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert main(["--file", str(prompt), "--max-lines", "2"]) == 0

    output = capsys.readouterr().out
    assert "WARN" in output
    assert "check_context_budget: PASS warning-only" in output

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

THRESHOLDS = {
    "AGENTS.md": 140,
    "MEMORY.md": 220,
    "docs/prompt-library.md": 340,
    "docs/agentops/sequential-chain-workflow.md": 220,
    "docs/agentops/subagent-playbook.md": 180,
    "docs/agentops/context-budgeting.md": 180,
}


def check_file(path: str, threshold: int) -> None:
    full_path = ROOT / path
    if not full_path.exists():
        print(
            f"WARN {path}: missing; threshold {threshold} lines; "
            "suggestion: create it only if this repo needs that context layer."
        )
        return

    line_count = len(full_path.read_text(encoding="utf-8").splitlines())
    status = "WARN" if line_count > threshold else "OK"
    remediation = (
        "split durable details into focused docs and keep this file as a map"
        if line_count > threshold
        else "no action needed"
    )
    print(
        f"{status} {path}: {line_count} lines; threshold {threshold}; "
        f"suggestion: {remediation}."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Warn when agent-facing context exceeds line budgets.")
    parser.add_argument("--file", type=Path, help="Check one prompt or doc file.")
    parser.add_argument("--max-lines", type=int, default=80, help="Line budget for --file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.file:
        path = args.file
        display = str(path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            print(f"WARN {display}: missing; threshold {args.max_lines} lines.")
        else:
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            status = "WARN" if line_count > args.max_lines else "OK"
            print(f"{status} {display}: {line_count} lines; threshold {args.max_lines}.")
    else:
        for path, threshold in THRESHOLDS.items():
            check_file(path, threshold)
    print("check_context_budget: PASS warning-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

THRESHOLDS = {
    "AGENTS.md": 140,
    "MEMORY.md": 220,
    "docs/prompt-library.md": 280,
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


def main() -> int:
    for path, threshold in THRESHOLDS.items():
        check_file(path, threshold)
    print("check_context_budget: PASS warning-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

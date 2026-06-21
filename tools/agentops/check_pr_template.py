from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"

REQUIRED = {
    "linked issue": ("linked issue", "closes #", "fixes #"),
    "dependency status": ("dependency status",),
    "owned files": ("owned files",),
    "validation": ("validation", "validation commands", "verification"),
    "concurrency risk": ("concurrency risk",),
}


def has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def main() -> int:
    if not TEMPLATE.exists():
        print("FAIL missing .github/PULL_REQUEST_TEMPLATE.md")
        return 1

    text = TEMPLATE.read_text(encoding="utf-8").lower()
    missing = [
        label
        for label, phrases in REQUIRED.items()
        if not has_any(text, phrases)
    ]

    if missing:
        for label in missing:
            phrases = ", ".join(REQUIRED[label])
            print(
                "FAIL .github/PULL_REQUEST_TEMPLATE.md missing "
                f"{label!r}; include one of: {phrases}"
            )
        print("check_pr_template: FAIL")
        return 1

    print("OK .github/PULL_REQUEST_TEMPLATE.md includes required PR fields")
    print("check_pr_template: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

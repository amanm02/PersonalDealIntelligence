from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.agentops.common import main_check


PRODUCT_TEST_FAILURE = "product test failure"
AGENTOPS_FAILURE = "AgentOps failure"
RUNNER_SETUP_FAILURE = "runner setup failure"
DEPENDENCY_INSTALL_FAILURE = "dependency install failure"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class FailureSummary:
    category: str
    reason: str
    markers: tuple[str, ...]


CLASSIFIERS: tuple[tuple[str, str, tuple[re.Pattern[str], ...]], ...] = (
    (
        DEPENDENCY_INSTALL_FAILURE,
        "dependency installation markers were found",
        (
            re.compile(r"no matching distribution found", re.IGNORECASE),
            re.compile(r"could not find a version that satisfies", re.IGNORECASE),
            re.compile(r"resolutionimpossible", re.IGNORECASE),
            re.compile(r"pip .*subprocess-exited-with-error", re.IGNORECASE),
            re.compile(r"failed to install", re.IGNORECASE),
            re.compile(r"npm err!", re.IGNORECASE),
            re.compile(r"yarn install.*failed", re.IGNORECASE),
        ),
    ),
    (
        RUNNER_SETUP_FAILURE,
        "runner or toolchain setup markers were found",
        (
            re.compile(r"no runner matching", re.IGNORECASE),
            re.compile(r"self-hosted runner", re.IGNORECASE),
            re.compile(r"unable to locate executable file", re.IGNORECASE),
            re.compile(r"version .* was not found in the local cache", re.IGNORECASE),
            re.compile(r"setup-python", re.IGNORECASE),
            re.compile(r"toolcache|tool cache", re.IGNORECASE),
            re.compile(r"no space left on device", re.IGNORECASE),
        ),
    ),
    (
        AGENTOPS_FAILURE,
        "AgentOps paths or commands failed",
        (
            re.compile(r"tools/agentops", re.IGNORECASE),
            re.compile(r"tests/agentops", re.IGNORECASE),
            re.compile(r"docs/agentops", re.IGNORECASE),
            re.compile(r"\bagentops\b", re.IGNORECASE),
            re.compile(r"\baudit_[a-z_]+", re.IGNORECASE),
            re.compile(r"\bcheck_context_budget\b", re.IGNORECASE),
            re.compile(r"\bworktree_report\b", re.IGNORECASE),
            re.compile(r"\bsummarize_ci_failure\b", re.IGNORECASE),
        ),
    ),
    (
        PRODUCT_TEST_FAILURE,
        "product test failure markers were found",
        (
            re.compile(r"FAILED tests/(?!agentops/)", re.IGNORECASE),
            re.compile(r"ERROR tests/(?!agentops/)", re.IGNORECASE),
            re.compile(r"src/pdi/", re.IGNORECASE),
            re.compile(r"\bpdi\.[a-z_]+", re.IGNORECASE),
            re.compile(r"python3 -m pytest(?! .*tests/agentops)", re.IGNORECASE),
        ),
    ),
)


def matching_lines(text: str, patterns: tuple[re.Pattern[str], ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in patterns):
            stripped = line.strip()
            if stripped and stripped not in matches:
                matches.append(stripped)
    return tuple(matches[:5])


def classify_ci_failure(text: str) -> FailureSummary:
    for category, reason, patterns in CLASSIFIERS:
        markers = matching_lines(text, patterns)
        if markers:
            return FailureSummary(category=category, reason=reason, markers=markers)
    return FailureSummary(
        category=UNKNOWN,
        reason="no known failure markers were found",
        markers=(),
    )


def read_input(values: list[str]) -> str:
    if not values:
        if sys.stdin.isatty():
            return ""
        return sys.stdin.read()

    chunks: list[str] = []
    for value in values:
        path = Path(value)
        if path.exists() and path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        else:
            chunks.append(value)
    return "\n".join(chunks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify CI logs into broad AgentOps triage categories."
    )
    parser.add_argument(
        "log",
        nargs="*",
        help="Log text or path(s) to local log fixture files. Reads stdin when omitted.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = read_input(args.log)
    summary = classify_ci_failure(text)

    print(f"classification: {summary.category}")
    print(f"reason: {summary.reason}")
    if summary.markers:
        print("markers:")
        for marker in summary.markers:
            print(f"- {marker}")
    else:
        print("markers: none")
    return main_check("summarize_ci_failure", [True])


if __name__ == "__main__":
    raise SystemExit(main())

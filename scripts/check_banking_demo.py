#!/usr/bin/env python3
"""Fresh-clone Banking MVP demo readiness gate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path("/tmp/pdi-banking-demo.sqlite")
DEFAULT_DIGEST = Path("/tmp/pdi-banking-demo-digest.md")
DEFAULT_AS_OF = "2026-06-18"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the local Banking MVP demo path."
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Demo SQLite path.")
    parser.add_argument(
        "--digest-output",
        default=str(DEFAULT_DIGEST),
        help="Demo digest artifact path.",
    )
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    args = parser.parse_args()

    db_path = Path(args.db)
    digest_path = Path(args.digest_output)

    _run_json(
        db_path,
        "banking",
        "demo",
        "--reset",
        "--seed",
        "fixtures",
        "--digest-output",
        str(digest_path),
        "--as-of",
        args.as_of,
        "--format",
        "json",
    )
    _assert(db_path.exists(), f"demo database was not created: {db_path}")
    _assert(digest_path.exists(), f"demo digest was not created: {digest_path}")

    checking = _find_one(
        db_path,
        "checking_bonus",
        "banking",
        "find",
        "--query",
        "checking bonus",
        "--subcategory",
        "checking_bonus",
        "--format",
        "json",
    )
    _find_one(
        db_path,
        "savings_bonus",
        "banking",
        "find",
        "--query",
        "savings",
        "--subcategory",
        "savings_bonus",
        "--format",
        "json",
    )
    _find_one(
        db_path,
        "brokerage_bonus",
        "banking",
        "find",
        "--subcategory",
        "brokerage_bonus",
        "--min-bonus",
        "500",
        "--format",
        "json",
    )

    _assert_search_result(checking)
    detail = _run_json(
        db_path,
        "banking",
        "show",
        str(checking["id"]),
        "--format",
        "json",
    )
    _assert_show_detail(detail)

    digest_path.unlink(missing_ok=True)
    _run(
        db_path,
        "banking",
        "digest",
        "--demo",
        "--output",
        str(digest_path),
        "--as-of",
        args.as_of,
    )
    _assert(digest_path.exists(), f"demo digest was not regenerated: {digest_path}")
    rendered_digest = digest_path.read_text(encoding="utf-8")
    _assert("# Banking Deal Digest" in rendered_digest, "digest markdown is invalid")

    print("Banking demo readiness check passed.")
    print(f"Database: {db_path}")
    print(f"Digest: {digest_path}")
    return 0


def _find_one(db_path: Path, expected_subcategory: str, *args: str) -> dict[str, Any]:
    rows = _run_json(db_path, *args)
    _assert(isinstance(rows, list), f"{expected_subcategory} find output is not a list")
    _assert(rows, f"{expected_subcategory} find returned no deals")
    match = rows[0]
    _assert(
        match.get("subcategory") == expected_subcategory,
        f"{expected_subcategory} find returned {match.get('subcategory')}",
    )
    return match


def _assert_search_result(row: dict[str, Any]) -> None:
    required = {
        "id",
        "institution_name",
        "subcategory",
        "bonus_amount_cents",
        "estimated_net_value_cents",
        "score_0_to_100",
        "score_band",
        "recommended_action",
        "review_indicator",
        "match_reason",
    }
    missing = sorted(required - set(row))
    _assert(not missing, f"find result missing fields: {', '.join(missing)}")
    _assert(
        row.get("source_name") or row.get("source_url"),
        "find result missing source label or URL",
    )


def _assert_show_detail(detail: dict[str, Any]) -> None:
    for field in (
        "status",
        "requirements",
        "source_urls",
        "evidence_references",
        "missing_data_warnings",
    ):
        _assert(field in detail, f"show output missing {field}")
    _assert(isinstance(detail["requirements"], dict), "show requirements invalid")
    _assert(
        detail["source_urls"] or detail["evidence_references"],
        "show output missing source/evidence references",
    )


def _run_json(db_path: Path, *args: str) -> Any:
    result = _run(db_path, *args)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"command did not return JSON: {' '.join(args)}\n{result.stdout}"
        ) from error


def _run(db_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    command = [
        sys.executable,
        "-m",
        "pdi",
        "--db",
        str(db_path),
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            "command failed: "
            f"{' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())

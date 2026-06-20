#!/usr/bin/env python3
"""
Create the PersonalDealIntelligence Track A/B issue batch in GitHub.

Requirements:
  - GitHub CLI installed: https://cli.github.com/
  - Authenticated with issue write access: gh auth login
  - Run from any directory:
      python3 create_pdi_github_issues.py pdi_github_issue_batch.json

This script creates issues sequentially and prints created URLs.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

def run(cmd):
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        print("Command failed:", " ".join(cmd), file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result.stdout.strip()

def main():
    batch_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pdi_github_issue_batch.json")
    data = json.loads(batch_path.read_text(encoding="utf-8"))
    repo = data["repo"]

    print("Checking GitHub CLI auth...")
    run(["gh", "auth", "status"])

    created = []
    for idx, issue in enumerate(data["issues"], 1):
        title = issue["title"]
        body = issue["body"]
        print(f"Creating {idx}/{len(data['issues'])}: {title}")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as tmp:
            tmp.write(body)
            tmp_path = tmp.name
        try:
            url = run(["gh", "issue", "create", "--repo", repo, "--title", title, "--body-file", tmp_path])
            created.append((title, url))
            print("  ->", url)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    print("\nCreated issues:")
    for title, url in created:
        print(f"- {title}: {url}")

if __name__ == "__main__":
    main()

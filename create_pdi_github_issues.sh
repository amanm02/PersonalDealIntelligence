#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/create_pdi_github_issues.py" "$SCRIPT_DIR/pdi_github_issue_batch.json"

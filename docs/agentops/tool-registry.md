# Tool Registry

Every tool should have one focused job and a predictable contract.

| Tool | Purpose | Access | Inputs | Outputs | Smoke test | Status |
|---|---|---|---|---|---|---|
| `tools/agentops/audit_docs.py` | Verify required docs and size guidance | read | repo files | pass/fail output | `make agentops-pr` | active |
| `tools/agentops/audit_memory.py` | Verify durable memory file presence and size guidance | read | `MEMORY.md` | pass/fail output | `make agentops-pr` | active |
| `tools/agentops/audit_structure.py` | Verify AgentOps structure anchors exist | read | repo files | pass/fail output | `make agentops-pr` | active |
| `tools/agentops/audit_tools.py` | Verify tool/function registries exist | read | repo files | pass/fail output | `make agentops-pr` | active |
| `tools/agentops/audit_hooks.py` | Verify hook config and registry | read | `.codex/hooks.json`, docs | pass/fail output | `make hooks-smoke` | active |
| `tools/agentops/audit_mcp.py` | Verify MCP registry presence | read | docs | pass/fail output | `make mcp-smoke` | active |
| `tools/agentops/hook_router.py` | Route Codex hook events to deterministic messages | read | hook event name | exit code and message | `make hooks-smoke` | active |
| `tools/agentops/check_context_budget.py` | Warn when agent entry docs or one prompt exceed context budget targets | read | repo docs or `--file` path | warning-only output | `make workflow-hygiene` | active |
| `tools/agentops/check_pr_template.py` | Verify PR template metadata required for review and concurrency | read | `.github/PULL_REQUEST_TEMPLATE.md` | pass/fail output | `make workflow-hygiene` | active |
| `tools/agentops/check_pr_body.py` | Verify an actual PR body contains review, CI, dependency, and concurrency metadata | read | local PR body file or optional `gh` PR lookup | pass/fail output | `python3 -m tools.agentops.check_pr_body --body-file /tmp/pdi-agentops-context/pr-body.md` | active |
| `tools/agentops/chain_status.py` | Summarize sequential issue/PR progress and closeout gaps | read | issue chain, optional offline issue/PR JSON, optional `gh` lookup | table plus pass/warn output | `make agentops-chain-status` | active |
| `tools/agentops/check_prompt_library.py` | Verify required workflow prompts exist and the implementation prompt includes state preflight markers | read | `docs/prompt-library.md` | pass/fail output | `make workflow-hygiene` | active |
| `tools/agentops/check_issue_hygiene.py` | Verify issue-hygiene docs or fixture/live issue bodies contain required implementation metadata sections | read | `docs/agentops/issue-hygiene.md`, optional fixture or `gh` issue | pass/fail output | `make workflow-hygiene` | active |
| `tools/agentops/check_issue_map_freshness.py` | Check issue-map concurrency scaffolding and optionally compare statuses with fixtures or GitHub | read | `docs/issue-map.md`, optional JSON fixture or `gh` | pass/fail output | `make workflow-hygiene` | active |
| `tools/agentops/check_generated_artifacts.py` | Block tracked or untracked Python cache artifacts before review | read | local git status and tracked file list | pass/fail output | `make workflow-hygiene` | active |
| `tools/agentops/check_work_state.py` | Report branch, dirty tree, divergence, and stale-branch suspicion | read | local git checkout | pass/fail or advisory output | `make workflow-hygiene` | active |
| `tools/agentops/worktree_report.py` | Report worktree hygiene warnings without deleting anything | read | local git worktrees | advisory output | `make workflow-hygiene` | active |
| `tools/agentops/summarize_ci_failure.py` | Classify CI logs into product, AgentOps, runner, dependency, or unknown failures | read | log text, stdin, or local log files | classification output | `python3 -m tools.agentops.summarize_ci_failure --help` | active |
| `tools/agentops/recommend_next_issue.py` | Rank the next likely safe issue from issue-map order, labels, dependencies, and optional GitHub issue state | read | `docs/issue-map.md`, optional fixture or `gh` issue list | recommendation output | `make workflow-hygiene` | active |
| `python3 -m pdi.storage` | Initialize local SQLite storage and seed fictional fixtures | read/write local db path | CLI args | SQLite file and stdout/stderr | `python3 -m pdi.storage init --db /tmp/pdi-repoos.sqlite --seed-fixture examples/banking_deals.json` | active |

## Tool standard

A tool is allowed only if:

- It does one job.
- Its name is action-oriented.
- Its inputs are explicit.
- Its outputs are predictable.
- It documents whether it reads or writes.
- Write actions use confirmation or a safe approval path.
- Problem modes are documented.
- A smoke test exists when practical.

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

# Recurring Audits

AgentOps CI uses an organization-level self-hosted runner from `amanm02` with labels `self-hosted`, `macOS`, and `ARM64`. Include runner availability in audit reviews.

## Every PR

Run:

```bash
make agentops-pr
```

Checks:

- `AGENTS.md` stays short and map-like.
- `MEMORY.md` remains durable.
- Changed files are reflected in the folder map if needed.
- New tools/functions have registries and tests.
- Hooks pass smoke checks.
- MCP registry is updated if MCP config changed.
- Docs are updated when behavior, commands, structure, tools, hooks, MCPs, runners, or workflows change.
- The organization-level self-hosted runner is available to `amanm02/PersonalDealIntelligence` before relying on Actions status.

## Weekly

Run:

```bash
make agentops-weekly
```

Checks:

- Stale docs
- Orphan docs
- Duplicate instructions
- Folder sprawl
- Prompt-library bloat
- Unused hooks, skills, or subagents
- Runner availability and expected labels

## Monthly

Run:

```bash
make agentops-monthly
```

Checks:

- Agent legibility score
- Harness health score
- MCP necessity
- Hook noise
- Top repeated agent defects
- Whether the organization-level runner remains the right default for this repo

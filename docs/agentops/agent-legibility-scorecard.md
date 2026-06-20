# Agent Legibility Scorecard

Score each area from 1 to 5. Initial scores are conservative and should be updated during monthly AgentOps review.

| Area | Score | Standard |
|---|---:|---|
| `AGENTS.md` clarity | 4 | Short, current, map-like |
| `MEMORY.md` quality | 3 | Durable, non-duplicative, current |
| Folder structure | 4 | Predictable, navigable, minimal orphan files |
| Verification commands | 4 | One clear path to prove current work |
| Prompt library | 3 | Reusable, current, not bloated |
| Hooks | 3 | Deterministic, useful, low-noise |
| MCPs | 3 | Necessary, documented, tested |
| Tool/function schemas | 2 | Explicit inputs, predictable outputs |
| Skills | 3 | Useful, scoped, discoverable |
| Subagents | 3 | Clear roles, not redundant |
| Eval coverage | 1 | Regression cases exist for known defects |
| Trace usage | 2 | Defects become improvements |

## Review cadence

- PR: check affected areas.
- Weekly: review stale docs and structure.
- Monthly: score all areas and update the improvement backlog.

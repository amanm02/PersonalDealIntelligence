# Agent Instructions

This file is the entry map for agents. Keep it short and use the linked docs as the source of truth.

## Read first

Before implementing a GitHub issue, read in this order:

1. `AGENTS.md`
2. `docs/issue-map.md`
3. `docs/verification.md`
4. `docs/architecture/banking-mvp.md`
5. `docs/decisions.md`
6. `MEMORY.md`
7. `docs/agentops/README.md`
8. The GitHub issue body
9. Any linked implementation plan
10. Only the files needed for the task

Do not read unrelated docs or expand scope unless the issue requires it.

## Project scope

Personal Deal Intelligence is currently the Banking MVP only. Included categories are checking, savings, checking plus savings bundles, brokerage bonuses, money market bonuses, and CD bonuses. Credit card sign-up bonuses are deferred banking-adjacent work.

Out of scope for the initial build: clothing, travel, flights, hotels, cashback stack optimization, browser extensions, automatic financial actions, private-session collection, source-access workarounds, credentials, and highly sensitive personal identifiers.

## Working rules

- Use the smallest safe change that satisfies the issue acceptance criteria.
- Keep source collection policy-driven and conservative.
- Keep tests offline by default unless an issue explicitly adds a disabled-by-default live integration test.
- Preserve raw evidence when extracting banking terms.
- Mark ambiguous terms as unknown instead of guessing.
- Update docs when behavior, structure, commands, tools, hooks, MCPs, runners, or workflows change.
- Run verification from `docs/verification.md` before claiming completion.
- Keep `.codex/`, `.agents/skills/`, `docs/agentops/`, and `tools/agentops/` generic unless a stable repo-specific override is required.

## AgentOps map

- `MEMORY.md` stores durable repo facts and repeated failure patterns only.
- `docs/agentops/` stores operating-layer registries, scorecards, runner notes, and recurring audit guidance.
- `.codex/` stores Codex config, hooks, rules, and subagent role prompts.
- `.agents/skills/` stores reusable agent skills.
- `tools/agentops/` stores deterministic audit and smoke-check scripts.

## Final response format

Every Codex final response must include:

```text
Summary
Files changed
Validation
Risks / follow-ups
```

Include exact validation commands and results. If validation could not be run, explain why.

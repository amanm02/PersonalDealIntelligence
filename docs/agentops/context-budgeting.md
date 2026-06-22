# Context Budgeting

Sequential chains fail slowly when every turn reloads the same background. Keep prompts and reports compact enough that the next agent can act without rehydrating the entire repository.

## Budgets

| Artifact | Target |
|---|---:|
| Chain implementation prompt | 90 lines |
| Chain review prompt | 70 lines |
| Subagent prompt | 45 lines |
| Blocker report | 35 lines |
| PR body | 80 lines |
| Final response | 50 lines |

Use the issue body as the source of truth instead of pasting it into prompts. Link docs by path and name only the files that matter for the active issue.

## Token Rules

- Read the standard source-of-truth docs once per chain setup, then rely on the issue contract for each issue.
- Do not paste `AGENTS.md`, `README.md`, or `docs/verification.md` into prompts when the agent can read them locally.
- Replace repeated boilerplate with template names from `docs/agentops/templates/`.
- Keep validation reports to command plus result. Put long logs in scratch files outside the repo.
- Summarize subagent findings as verdicts, not transcripts.
- Stop writing narrative final reports once the required sections are satisfied.

The recent two-thread chain produced 6,131 parsed event records and session token counters dominated by cached input. Caching reduced repeated input cost, but the sessions still paid in latency, compaction, and review difficulty. Avoid embedding full chain history in every issue prompt.

## Prompt-Length Check

Check a prompt or template before reuse:

```bash
python3 -m tools.agentops.check_context_budget --file docs/agentops/templates/chain-implementation-prompt.md --max-lines 90
```

The check is warning-only so it can guide prompt trimming without blocking urgent work.

## Anti-Patterns

- Repeating issue-body acceptance criteria in the hub prompt and every spoke prompt.
- Re-running broad preflight commands after every small patch when the state has not changed.
- Asking two spokes to perform dependency audits for the same issue.
- Copying full validation logs into PR bodies.
- Reporting every file read instead of the decision it enabled.

# Sequential Chain Retrospective

## Scope

This retrospective covers the recent dependency-chain campaign:

```text
#69 -> #72 -> #78 -> #81 -> #68 -> #71 -> #77 -> #80 -> #70 -> #73 -> #79 -> #82 -> #83 -> #34/24A -> #74 -> #75
```

The goal is AgentOps improvement only. It does not change product behavior, schemas, extraction, scoring, source policy, CLI product behavior, or fixtures.

## Sources reviewed

- `AGENTS.md`, `README.md`, `docs/issue-map.md`, `docs/verification.md`, `docs/architecture/banking-mvp.md`, `docs/decisions.md`, `MEMORY.md`, and `docs/agentops/README.md`.
- `docs/agentops/current-work-batches.md`, `docs/agentops/concurrency.md`, `docs/agentops/issue-hygiene.md`, `docs/prompt-library.md`, and `.codex/` rules/hooks.
- GitHub issue and PR metadata for #69, #72, #78, #81, #68, #71, #77, #80, #70, #73, #79, #82, #83, #34, #74, and #75.
- PR bodies and comments for PR #85, #86, #87, #92, #119, #120, #121, #123, #124, #125, #126, #127, #128, #129, #130, and #131.
- Local `chain-implementation-plan.md` as an untracked implementation note.
- Full local Codex JSONL session logs for:
  - `019eeb7c-1ca8-7d43-a223-216a9d542008`, "Implement issue chain"
  - `019eed46-fcb5-7120-b889-5f6ededced02`, "Implement issue chain 2"

The Codex thread reader returned compacted/truncated pages for these large sessions, so the review used the raw JSONL logs under `~/.codex/sessions/2026/06/21/`. Every JSONL record was parsed into a scratch event ledger. The ledger covered 6,131 records total: 3,496 records in the first thread and 2,635 records in the second thread.

Event counts reviewed:

| Thread | Records | Tool calls | Subagent spawns | Subagent closes | Waits | Patches | Context compactions |
|---|---:|---:|---:|---:|---:|---:|---:|
| Implement issue chain | 3,496 | 701 | 46 | 43 | 18 | 144 | 3 |
| Implement issue chain 2 | 2,635 | 547 | 26 | 20 | 19 | 102 | 2 |

Token counters in the logs reached about 74.4M total session tokens in the first thread and 55.2M in the second thread, dominated by cached input. Treat those as event-log counters rather than billing math; they are still strong evidence of repeated context rehydration.

## What worked

- The issue sequence was executable. Most child issues had concrete labels, acceptance criteria, and validation commands.
- One PR per issue kept review scope understandable even through schema, storage, extraction, scoring, CLI, and QA changes.
- Early stacking reduced idle time while prerequisite evidence/persistence changes were still landing.
- Thread 2 improved the operating model by using cleaner worktrees, waiting for merges more often, and reducing subagent volume from 46 spawns to 26.
- Validation quality was high: PR bodies consistently named focused tests, full `python3 -m pytest`, and `git diff --check`; early PRs also ran `make agentops-pr`.
- Post-diff review spokes found real defects, including unsafe unknown defaults, debit-card purchase routing risk, card identity gaps, migration/test gaps, missing `scored_as_of`, and QA scenario-gating omissions.
- The campaign preserved project safety boundaries: no live source collection, credentials, private sessions, applications, or financial actions were introduced by the workflow.

## Wasted token usage

- The campaign prompts repeated the full chain, constraints, branch names, subagent roles, validation ladder, and PR body shape. Those details now belong in short templates and chain contract tables.
- Issue bodies were often around 75 to 131 lines and were restated in hub prompts, issue contract extraction, PR bodies, and final reports.
- The first thread mentioned early issues hundreds of times while later issues were still not active. This inflated cached input and made compaction necessary three times.
- Repeated repo-state verification appeared in every issue even when the hub had just verified state and no merge had occurred.
- Subagents often read the same docs and restated the same dependency chain. The first thread used 46 spawn calls and hit agent-limit events; several agents had to be closed just to continue.
- PR bodies and final reports sometimes copied validation narratives where command plus result would have been enough.
- The PR body checker expected the full repo template, while the campaign used compact PR bodies. Agents had to expand temporary bodies or rerun checks instead of using a chain-specific contract.

## Wasted time

- Stacked PRs #86, #87, #92, #119, #120, #121, and #123 targeted dependency branches and several lacked closing references. #80 was still open in preflight despite merged PR #123.
- The first stack opened four dependent PRs (#85, #86, #87, #92) before stopping. When #92 conflicted after earlier dependency merges, the hub first rebased onto `origin/main`, then had to repair the base to the merged dependency branch and force-push.
- Later in the first thread, #80 resumed from a branch-base mismatch because the local branch pointed at an older local #77 commit while the remote branch had the merged dependency tip.
- The #80 -> #70 transition was allowed because file ownership was disjoint, but #73 had to stop after a spoke found overlap with open PR #123.
- Thread 2 reduced branch conflict churn but increased explicit wait/merge loops. Its event log still had 84 wait keyword hits and 291 merge keyword hits.
- Full-suite validation was repeated frequently. That was appropriate for storage/runtime changes, but later similar QA and docs changes could have used focused checks until a chain gate.
- Local worktree dirt from prior campaign branches created repeated advisory noise in `git status`, `check_work_state`, and `worktree_report`.
- PR/status checks were re-run manually in several places where one chain-status summary would have shown the same dependency picture.

## Subagent findings

Subagents helped when they answered a narrow question:

- issue readiness and stale dependency checks;
- file ownership and blocked-file risk;
- focused test planning;
- post-diff scope review;
- failure triage after validation output.

Concrete helpful findings from the logs included:

- #73 review flagged credit-card field defaults, evidence span preservation, and debit-card purchase misrouting risks.
- #79 review flagged missing conservative card identity handling.
- #71 review flagged link/trust metadata and migration/foreign-key test gaps.
- #77 review flagged missing run-history timestamp coverage.
- #74 review flagged missing scenario failure handling.
- #75 review flagged a useful optional conflict-negative test.

Subagents hurt when they produced broad plans:

- overlapping dependency summaries for issues already ordered by the chain;
- duplicate restatements of issue bodies and repo safety rules;
- validation recommendations that repeated `docs/verification.md` without choosing the narrow subset;
- planning future dependent issues before the active issue had merged;
- agent-pool management overhead in the first thread, including explicit agent-limit events.

## Better workflow

- Use one hub for the whole chain. The hub owns state, branch strategy, PRs, validation, and issue closeout.
- Convert the chain into a compact issue contract table once. Update the row after each merge instead of rewriting prompts.
- Use at most two setup spokes before implementation and one post-diff spoke before commit. Close spokes immediately after their finding is captured.
- Use spokes only for dependency audit, file ownership audit, test planning, failure triage, and post-diff review.
- Stack only when the next issue truly requires unmerged dependency code. Stop before opening a fourth dependent PR.
- Put `Closes #<issue>` in every issue PR, including stacked PRs, unless the PR intentionally does not close the issue.
- After every merge, run a chain-status check and reconcile open issues before starting the next dependent issue.
- Use focused validation while developing and reserve full `python3 -m pytest` plus `make agentops-pr` for PR creation, high-risk surfaces, and stack-collapse gates.
- Keep prompts under the budgets in `docs/agentops/context-budgeting.md`.
- Stop when issue bodies lack contracts, branch depth gets too high, validation fails twice for the same unclear reason, or implementation needs blocked product scope.

## New infrastructure added

- `docs/agentops/sequential-chain-workflow.md` defines the hub-and-spoke chain workflow, stacking guidance, validation cadence, and stop rules.
- `docs/agentops/subagent-playbook.md` defines when spokes help, when they hurt, and the output contract for useful spokes.
- `docs/agentops/context-budgeting.md` defines prompt, blocker, PR, and final-report budgets.
- `docs/agentops/templates/` contains compact chain implementation, review, subagent audit, blocker report, issue contract, and PR body templates.
- `tools/agentops/chain_status.py` summarizes issue/PR chain progress and detects merged-PR/open-issue closeout gaps.
- `tools/agentops/check_pr_body.py --chain --require-closure` validates compact chain PR bodies.
- `tools/agentops/check_context_budget.py --file ... --max-lines ...` checks individual prompt/template length.
- Makefile targets expose `agentops-chain-status`, `agentops-issue-contracts`, `agentops-context-budget`, and `agentops-pr-body`.

## Remaining follow-ups

- Reconcile GitHub issue #80, which was still open in preflight even though PR #123 was merged.
- Consider closing or pruning stale local `.worktrees/` directories after human confirmation.
- For the next dependency campaign, create an offline chain-status fixture from preflight output and attach it to the planning note or PR.
- Consider an issue rewrite pass for broad future issues before another long implementation campaign.

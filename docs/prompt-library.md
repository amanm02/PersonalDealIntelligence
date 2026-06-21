# Prompt Library

This file stores reusable prompts for implementation agents.

Keep prompts compact. Point to source-of-truth files instead of embedding long context.

## Use rules

- Use the smallest prompt that can complete the task.
- Include the GitHub issue number.
- Treat the GitHub Issue body as the implementation prompt.
- Do not add a separate implementation-prompt section inside Issue bodies.
- Read source-of-truth files first.
- Do not paste large docs unless the agent cannot access them.
- Ask for evidence, validation, and risks in the output.
- Do not expand beyond the issue scope.
- Keep Banking MVP work separate from future clothing, travel, flight, hotel, and shopping work.
- Treat credit-card acquisition offers as Banking MVP scope, but implement them only through the dedicated credit-card/source/taxonomy/scoring issues.

## Prompt: implement a GitHub issue

```text
Work on GitHub issue #<ISSUE_NUMBER>.

Preflight:
- Run `python3 -m tools.agentops.check_work_state --advisory` before editing.
- Confirm issue state, dependencies, owned files, and blocked files.
- Stop if the issue is closed, blocked, needs rewrite, stale in `docs/issue-map.md`, or already covered by an open PR.

Read in order:
1. AGENTS.md
2. docs/issue-map.md
3. docs/verification.md
4. docs/architecture/banking-mvp.md
5. docs/decisions.md
6. MEMORY.md
7. docs/agentops/README.md
8. docs/agentops/issue-hygiene.md
9. The issue body
10. Any linked implementation plan
11. Only the files needed for the task

Implement the smallest safe change that satisfies the issue acceptance criteria.
Do not expand scope.
Do not add non-MVP deferred categories.
Run the relevant validation from docs/verification.md.
Final response must include Summary, Files changed, Validation, and Risks / follow-ups.
```

## Prompt: create an implementation plan

```text
Create an implementation plan for GitHub issue #<ISSUE_NUMBER>.

Read AGENTS.md, docs/issue-map.md, docs/verification.md, docs/architecture/banking-mvp.md, docs/decisions.md, and the issue body.
Do not edit production code.
Create or update a plan in docs/implementation-plans/active/.

The plan must include:
- problem
- current state
- desired state
- proposed changes
- files to edit
- tests
- validation commands
- rollback
- open questions
- checklist

Keep the plan scoped to the issue.
```

## Prompt: review a pull request

```text
Review PR #<PR_NUMBER> for correctness, scope control, safety boundaries, duplication, and validation quality.

Read AGENTS.md, docs/issue-map.md, docs/verification.md, docs/architecture/banking-mvp.md, the PR diff, linked issue, and any linked implementation plan.
Compare against recently closed PRs if overlap is possible.

Return findings grouped as:
- Blockers
- Non-blocking issues
- Validation gaps
- Safety/compliance concerns
- Suggested follow-ups

Do not make edits.
```

## Prompt: fix failing CI or validation

```text
Fix the failing checks for PR #<PR_NUMBER> or issue #<ISSUE_NUMBER>.

Read AGENTS.md and docs/verification.md first.
Inspect the failing job logs or local validation output first.
Reproduce the failing command locally if possible.
Make the smallest safe fix.
Run the failing command again and report the exact validation result.
Do not expand scope beyond the failure.
```

## Prompt: audit Banking MVP readiness

```text
Audit the Banking MVP for readiness.

Read AGENTS.md, README.md, docs/issue-map.md, docs/verification.md, docs/architecture/banking-mvp.md, docs/decisions.md, docs/release-checklists/banking-mvp.md, and the current implementation files.
Do not edit files.

Return:
- readiness summary
- blockers
- missing tests
- stale docs
- safety/compliance gaps
- recommended issue list
- highest-leverage next PR
```

## Prompt: deduplicate open work

```text
Compare all open PRs against open issues, closed PRs, and docs/issue-map.md.
Identify duplicates, stale branches, overlapping scopes, and PRs that should be closed, rebased, merged, or split.
Do not make changes.

Return a table with:
- PR
- linked issue
- status
- overlap evidence
- risk
- recommended action
```

## Prompt: implement source policy safely

```text
Work on source policy for GitHub issue #<ISSUE_NUMBER>.

Read AGENTS.md, docs/issue-map.md, docs/verification.md, docs/architecture/banking-mvp.md, docs/decisions.md, and the issue body.

Implement source policy config and validation only.
Do not collect live data.
Do not add browser automation.
Do not add proxy support.
Do not bypass source restrictions.

Validation must prove unsafe configs are blocked.
```

## Prompt: implement extractor safely

```text
Work on banking extraction for GitHub issue #<ISSUE_NUMBER>.

Read AGENTS.md, docs/issue-map.md, docs/verification.md, docs/architecture/banking-mvp.md, docs/decisions.md, storage models, raw snapshot models, and the issue body.

Use local fixtures.
Preserve evidence spans where possible.
Leave missing terms unknown.
Do not guess high-impact banking terms.
Do not make live network calls.

Validation must include fixture tests and non-deal rejection or low-confidence handling.
```

## Prompt: implement scoring transparently

```text
Work on banking scoring for GitHub issue #<ISSUE_NUMBER>.

Read AGENTS.md, docs/issue-map.md, docs/verification.md, docs/architecture/banking-mvp.md, docs/decisions.md, scoring config, canonical deal models, and the issue body.

Implement transparent component-level scoring.
Do not present output as financial advice.
Expose missing data warnings.
Use deterministic tests.

Validation must prove config changes affect scores predictably.
```

## Prompt: current-state preflight

```text
Run a current-state preflight for <BRANCH_OR_WORKTREE>.

Scope: inspect repository state only; do not edit files, fetch remote data only if explicitly approved, and do not change branches.
Read order: AGENTS.md, docs/verification.md, docs/issue-map.md, docs/agentops/README.md, then only files needed to explain the current state.
Required commands: pwd; git branch --show-current; git status --short; git log --oneline -5; git diff --stat; git diff --check.
Stop conditions: stop if the worktree is not the requested path, the branch is unexpected, uncommitted edits are unrelated or unexplained, or required source-of-truth docs are missing.
Final response format: Summary, Current state, Validation commands/results, Risks / follow-ups.
```

## Prompt: Verification-only review

```text
Run a verification-only review for PR #<PR_NUMBER> or issue #<ISSUE_NUMBER>.

Scope: verify the existing changes; do not edit files, rework scope, or implement missing features.
Read order: AGENTS.md, docs/verification.md, linked issue, PR diff or local diff, and only touched files needed to judge validation.
Required commands: git status --short; git diff --stat; git diff --check; then the smallest relevant commands from docs/verification.md.
Stop conditions: stop if the checkout is dirty with unrelated edits, the linked issue or PR diff is unavailable, validation would require live network not requested by the issue, or failures are unrelated to the reviewed changes.
Final response format: Summary, Files reviewed, Validation commands/results, Risks / follow-ups.
```

## Prompt: issue audit/rewrite

```text
Audit and rewrite GitHub issue #<ISSUE_NUMBER> for implementation readiness.

Scope: improve the issue body only; do not edit product code, tests, docs outside the issue body, or create an implementation plan unless requested.
Read order: AGENTS.md, docs/issue-map.md, docs/verification.md, docs/architecture/banking-mvp.md, docs/decisions.md, current issue body.
Required commands: git status --short; rg -n "#<ISSUE_NUMBER>|<KEY_TERMS>" docs README.md AGENTS.md MEMORY.md.
Stop conditions: stop if the issue conflicts with Banking MVP scope, duplicates active work, needs product decisions not present in docs/decisions.md, or acceptance criteria cannot be made testable.
Final response format: Summary, Rewritten issue body, Validation commands/results, Risks / follow-ups.
```

## Prompt: Next-issue selection

```text
Select the next GitHub issue to work on.

Scope: recommend only; do not edit files, assign issues, create branches, or start implementation.
Read order: AGENTS.md, docs/issue-map.md, docs/verification.md, docs/agentops/README.md, open issues, open PRs, recent merged PRs if overlap is possible.
Required commands: git status --short; gh issue list --state open --limit 100; gh pr list --state open --limit 100; python3 -m tools.agentops.recommend_next_issue --github.
Stop conditions: stop if GitHub access is unavailable, issue-map status appears stale, open PRs already cover the top candidate, dependencies are unclear, or the issue list may be truncated.
Final response format: Summary, Recommended next issue, Evidence, Validation commands/results, Risks / follow-ups.
```

## Prompt: Concurrency planning

```text
Create a concurrency plan for a bounded AgentOps or implementation batch.

Scope: plan parallel work only; do not edit files, create branches, or assign ownership outside the requested batch.
Read order: AGENTS.md, docs/issue-map.md, docs/verification.md, docs/agentops/README.md, target issue bodies, open PRs, changed-file summaries for related branches.
Required commands: git status --short; gh issue list --state open --limit 100; gh pr list --state open --limit 100; git diff --stat origin/main...HEAD when local branch context exists.
Stop conditions: stop if two agents need the same owned file, merge order is ambiguous, a prerequisite PR is not merged, the issue list may be truncated, or the batch would touch product behavior without explicit issue scope.
Final response format: Summary, Agent lanes, Owned files, Merge order, Validation commands/results, Risks / follow-ups.
```

## Prompt: CI failure triage

```text
Triage CI failures for PR #<PR_NUMBER>.

Scope: classify failures and propose the smallest next action; do not edit files unless separately asked to fix.
Read order: AGENTS.md, docs/verification.md, PR checks, failing job logs, PR diff, linked issue, runner docs if the failure is AgentOps runner-related.
Required commands: git status --short; gh pr checks <PR_NUMBER>; gh run view <RUN_ID> --log-failed; reproduce the failing local command when it is offline and deterministic.
Stop conditions: stop if logs are unavailable, the failure requires credentials or live services, the failure is from unrelated main breakage, or runner/toolcache symptoms make product fixes unsafe.
Final response format: Summary, Failure classification, Evidence, Validation commands/results, Risks / follow-ups.
```

## Prompt: worktree/branch hygiene review

```text
Review worktree and branch hygiene before starting or merging work.

Scope: inspect branches, worktrees, and local diffs only; do not delete worktrees, reset branches, or switch branches without explicit approval.
Read order: AGENTS.md, docs/verification.md, docs/agentops/README.md, docs/issue-map.md, then branch-specific issue or PR context if known.
Required commands: pwd; git worktree list; git branch --show-current; git status --short; git branch -vv; git diff --stat; git diff --check.
Stop conditions: stop if the active directory is not the requested worktree, the branch tracks the wrong remote, unowned edits are present, or branch purpose cannot be mapped to an issue/PR.
Final response format: Summary, Hygiene findings, Validation commands/results, Risks / follow-ups.
```

## Prompt: AgentOps audit follow-up

```text
Implement a small AgentOps audit follow-up for issue #<ISSUE_NUMBER>.

Scope: AgentOps docs/tooling only; do not change product behavior, banking logic, fixtures, or unrelated workflow files.
Read order: AGENTS.md, docs/issue-map.md, docs/verification.md, MEMORY.md, docs/agentops/README.md, issue body, linked audit or implementation plan, then only owned files.
Required commands: git status --short before editing; after editing run git status --short; git diff --stat; git diff --check; plus any targeted offline check named by docs/verification.md or the issue.
Stop conditions: stop if requested files are owned by another active agent, the change would duplicate an open PR, the issue requires product scope, or validation would need live credentials.
Final response format: Summary, Files changed, Validation commands/results, Risks / follow-ups.
```

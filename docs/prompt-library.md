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

Read in order:
1. AGENTS.md
2. docs/issue-map.md
3. docs/verification.md
4. docs/architecture/banking-mvp.md
5. docs/decisions.md
6. The issue body
7. Any linked implementation plan
8. Only the files needed for the task

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

## Prompt: concurrency planning

```text
Plan safe parallel work for GitHub issue #<ISSUE_NUMBER>.

Read AGENTS.md, docs/issue-map.md, docs/agentops/concurrency.md, docs/agentops/issue-hygiene.md, and docs/agentops/current-work-batches.md.
Verify current GitHub issue and PR state before trusting old issue text.

Return dependencies, owned files, blocked files, safe concurrent issues, unsafe overlaps, validation gates, and merge order.
Do not edit files.
```

## Prompt: issue rewrite

```text
Rewrite GitHub issue #<ISSUE_NUMBER> for safe Codex implementation.

Read docs/agentops/issue-hygiene.md and docs/agentops/concurrency.md.
Keep the issue scoped to one PR.
Add dependencies, owned files, blocked files, validation commands, stop conditions, concurrency label guidance, and PR body requirements.
Do not add product behavior beyond the original issue intent.
```

## Prompt: issue verification

```text
Verify GitHub issue #<ISSUE_NUMBER> before implementation.

Read AGENTS.md, docs/issue-map.md, docs/verification.md, docs/agentops/issue-hygiene.md, and the issue body.
Check dependency state, duplicate open PRs, owned/blocked file clarity, validation commands, safety boundaries, and stale roadmap references.

Return pass/fail with exact blockers and recommended rewrite or close action.
Do not edit files.
```

## Prompt: batch verification

```text
Verify the current work batch.

Read docs/agentops/concurrency.md, docs/agentops/current-work-batches.md, docs/issue-map.md, and open GitHub PR/issue state.
Confirm each batch item has dependencies, owned files, blocked files, validation gates, concurrency safety, and merge order.

Return the safe schedule, exclusive work, stale entries, and required validation.
Do not edit files.
```

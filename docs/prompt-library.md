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

## Prompt: implement a GitHub issue

```text
Work on GitHub issue #<ISSUE_NUMBER> in amanm02/PersonalDealIntelligence.

Start conditions:
- Start from latest origin/main.
- Confirm working tree is clean.
- Create branch: codex/issue-<ISSUE_NUMBER>-<short-slug>.
- Read AGENTS.md, the issue body, and only the relevant sections of docs/verification.md.
- Read architecture/decisions/config/schema docs only if this issue touches those areas.

Task:
- Implement the smallest safe change satisfying the issue acceptance criteria.
- Do not implement dependency issues.
- Do not expand product scope.
- Do not add live network behavior unless the issue explicitly requires it and tests remain disabled/offline by default.
- Preserve local-first SQLite/Python conventions.

Before editing:
- Identify owned files.
- Identify likely tests.
- Confirm whether dependencies are already implemented.
- Stop and report if dependency work is missing, scope conflicts with docs, or implementation would require unsafe source access.

Validation:
- Run targeted tests for changed code.
- Run broader validation from docs/verification.md when touching core flow, CLI, schema, source policy, scoring, digest, or docs.
- Report exact commands and results.

Completion:
- Commit changes.
- Push branch.
- Open PR against main.
- PR body must include linked issue, summary, files changed, validation, risks/follow-ups.
```

## Prompt: create an implementation plan

```text
Create an implementation plan for GitHub issue #<ISSUE_NUMBER>.

Do not edit production code.

Read:
- AGENTS.md
- issue body
- relevant docs/verification.md section
- relevant source files/tests only

Write docs/implementation-plans/active/issue-<ISSUE_NUMBER>.md with:

1. Objective
2. Current state evidence
3. Dependencies and blockers
4. Scope boundaries / non-goals
5. Owned files
6. Files to inspect but avoid editing unless necessary
7. Proposed data/API/CLI changes
8. Tests to add/update
9. Validation commands
10. Docs updates
11. Rollback plan
12. Stop conditions
13. Implementation checklist

Stop conditions:
- dependency issue not implemented;
- docs conflict with issue;
- required schema decision missing;
- live-source behavior is ambiguous;
- expected files overlap with an active PR.
```

## Prompt: review a pull request

```text
Verify PR #<PR_NUMBER> / issue #<ISSUE_NUMBER>.

Do not edit files.

Read:
- AGENTS.md
- issue body
- PR diff
- relevant docs/verification.md section
- changed tests and changed source files

Check:
- Scope matches issue.
- No dependency issue was reimplemented.
- Docs changed when behavior changed.
- Tests cover acceptance criteria.
- Offline-default behavior is preserved.
- Safety/source-policy boundaries are intact.
- Validation commands were actually run and reported.

Return:
- Pass/fail verdict
- Blockers
- Non-blocking issues
- Missing validation
- Regression risks
- Recommended merge/hold decision
```

## Prompt: fix failing CI or validation

```text
Clean up PR #<PR_NUMBER> without expanding scope.

Read:
- AGENTS.md
- PR diff
- linked issue
- failed review comments or validation output

Tasks:
- Remove unrelated changes.
- Fix failing validation.
- Update docs only for changed behavior.
- Keep branch based on latest main unless the PR is intentionally stacked.
- Run the previously failing checks plus relevant targeted tests.

Stop if:
- fix requires changing issue scope;
- dependency issue is missing;
- unrelated tests fail and cannot be attributed to this PR.

Return Summary, Files changed, Validation, Risks/follow-ups.
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

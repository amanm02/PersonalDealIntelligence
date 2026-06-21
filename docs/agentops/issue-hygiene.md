# Issue Hygiene

Issues should be directly usable as Codex implementation prompts and safe to schedule with nearby work.

## Standard Issue Contract

Every implementation issue should include:

- Dependencies: required issues, PRs, docs, or branch state.
- Owned files: exact files or file families the agent may edit.
- Blocked files: files or surfaces that must not be touched.
- Allowed files: narrow shared docs or checks that may be updated when needed.
- Validation commands: exact commands expected before PR creation.
- Stop conditions: when the agent must pause and report instead of editing.
- Split, rewrite, or close criteria: when the issue is too broad, stale, or already implemented.
- Concurrency guidance: `concurrency:exclusive`, `concurrency:parallel-safe`, or a clear prose equivalent.
- PR body fields: linked issue, dependency status, owned files, validation, concurrency risk, and safety notes.

## Stop Conditions

Stop before editing when:

- The working tree has unrelated uncommitted work.
- A dependency issue or PR is not in the expected state.
- An open PR already implements the issue.
- Required edits touch blocked files.
- Product runtime, schema, CLI, source policy behavior, collectors, extractors, scoring, workflows, or roadmap files are needed but not listed in scope.
- The issue asks for live network, credential, browser-session, financial-action, or source-access workaround behavior.

## Split, Rewrite, Or Close

- Split issues that mix schema, CLI, source policy, scoring, docs, and workflow changes.
- Rewrite issues with stale dependencies, unclear owned files, or missing validation gates.
- Close issues that are fully implemented by a merged PR.
- Keep follow-up issues explicit instead of expanding the current PR.

## Concurrency Labels

- `concurrency:exclusive`: shared files, schema, CLI, source policy, workflows, roadmap, or broad docs.
- `concurrency:parallel-safe`: narrow files with no shared contracts and independent tests.
- `blocked`: dependency is not merged or issue needs a rewrite before implementation.
- `needs-rewrite`: issue body is not safe as an implementation prompt.

## Copy-Paste Metadata Template

```md
## Dependencies
- Depends on:
- Must verify before editing:

## Owned files
- 

## Blocked files
- 

## Allowed shared files
- 

## Validation commands
- 

## Stop conditions
- Stop if:

## Split / rewrite / close criteria
- Split if:
- Rewrite if:
- Close if:

## Concurrency
- Label:
- Safe to run with:
- Must not run with:

## Required PR body fields
- Linked issue:
- Dependency status:
- Owned files:
- Blocked files touched:
- Validation commands and results:
- Concurrency risk notes:
- Safety / non-goals:
```

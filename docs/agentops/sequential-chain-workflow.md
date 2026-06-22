# Sequential Chain Workflow

Use this workflow for dependency chains where each issue depends on the previous issue's product or contract changes.

## Operating Model

The default shape is one hub and narrow spokes.

- The hub owns the active branch, edits, validation, PR body, merge-order decision, and issue closeout check.
- Spokes are read-only unless the hub delegates a single patch with exact files.
- Keep at most two setup spokes active before implementation and one post-diff spoke before commit.
- Close spokes as soon as their finding is captured.
- Dependent implementation issues are not coded concurrently.
- Parallelism is for audit, test planning, failure triage, and post-diff review.
- Every issue keeps its own PR unless a docs-only closeout explicitly groups work.

## Chain Setup

Before the first implementation PR:

1. Fetch and inspect current GitHub issue and PR state.
2. Convert the chain into an issue table with dependencies, owned files, blocked files, validation, and stop conditions.
3. Confirm broad parent issues have executable child issues. Do not implement broad parents directly.
4. Decide whether the first segment is main-targeted or stacked.
5. Save only short scratch notes outside the repo unless the issue asks for docs changes.

Use:

```bash
python3 -m tools.agentops.chain_status --chain "69,72,78,81,68,71,77,80,70,73,79,82,83,34,74,75" --github
```

Use `--issues-json` and `--prs-json` fixtures for offline repeat checks.

## Execution Checklist

For each issue:

1. Read the issue body and source-of-truth docs from `AGENTS.md`.
2. Extract the issue contract: objective, dependencies, owned files, blocked files, validation, stop conditions, and deferred scope.
3. Run at most two setup spokes: dependency/file ownership and test plan. Use one post-diff spoke after implementation when risk warrants it.
4. Stop if dependencies are stale, an open PR already covers the issue, or implementation would touch blocked files.
5. Implement the smallest change for the active issue only.
6. Run focused validation first, then shared gates when the touched surface warrants them.
7. Run post-diff review before commit.
8. Put `Closes #<issue>` in every PR body unless the PR intentionally does not close an issue.
9. After merge, verify the issue closed and the next issue's dependency is actually satisfied.

## PR Stacking

Stack when the next issue needs unmerged code from the previous issue and waiting would leave the hub idle.

Do not stack when:

- the next issue touches schema, CLI command shape, source policy, scoring assumptions, or shared workflow docs without a stable base;
- reviewers need a clean diff against `main`;
- a fourth open dependent PR would be required;
- a conflict requires repeated rebases;
- the stacked PR cannot include a clear base branch and dependency note.

For stacked PRs:

- Target the dependency branch, not `main`.
- Name the base PR and branch in the PR body.
- Include `Closes #<issue>` anyway. The recent chain left #80 open after PR #123 merged because several stacked PRs lacked closure references.
- After the stack merges, run `chain_status` and close/reconcile any issue that did not auto-close.

The #69/#72/#78/#81 thread opened four dependent PRs before stopping, then needed rebase repair when the stack was partially merged through dependency branches. Future chains should stop before opening the fourth dependent PR unless a reviewer explicitly asks for a deeper stack.

Thread 2 used cleaner per-issue worktrees and more merge waits. That reduced stack repair, but it still spent time polling merge state. Prefer waiting for merge when the next issue does not need unmerged code; otherwise stack only one or two issues ahead with explicit base PRs.

## Validation Cadence

Use validation proportional to risk:

- Before editing: status checks and issue contract only.
- During implementation: focused tests for the changed layer.
- Before PR: `git diff --check`, focused tests, and any issue-specific commands.
- Before final merge or after a stack collapses onto `main`: full `python3 -m pytest` and `make agentops-pr`.

Avoid blindly repeating the full suite after every tiny doc or fixture-only edit when a focused check proves the surface and a later chain gate will run the full suite. Do run the full suite when storage, CLI output, scoring, extraction, dedupe, fixtures, or shared test harness behavior changes.

Before opening a chain PR, validate the compact PR body:

```bash
python3 -m tools.agentops.check_pr_body --body-file docs/agentops/templates/pr-body-chain.md --chain --require-closure
```

## Stop Rules

Stop and file a blocker report when:

- a dependency is open, stale, or merged without the required behavior;
- an issue body lacks owned files, blocked files, validation, or stop conditions;
- implementation needs product behavior outside the issue;
- a stacked branch would become fourth-or-deeper;
- local validation fails twice for the same unclear reason;
- a spoke produces only broad restatement instead of a narrow finding.

Use `docs/agentops/templates/blocker-report.md`.

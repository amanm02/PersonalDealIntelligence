# Concurrency Operating Model

This model keeps parallel Codex work safe for Personal Deal Intelligence. It is for repository work only; it does not change product behavior.

## Parallelism

- Run at most three implementation agents at a time when owned files do not overlap.
- Run at most five read-only audit or review agents at a time.
- Keep total active subagents at six or fewer.
- Run only one agent at a time for schema, migrations, CLI command shape, source policy, workflows, roadmap, or shared documentation.
- Treat any issue labeled `concurrency:exclusive`, `blocked`, or `needs-rewrite` as exclusive until the issue body states otherwise.

## Safe And Unsafe Parallel Work

Safe parallel work has separate owned files, separate validation commands, and no shared migration, CLI, config, workflow, or roadmap edits.

Unsafe parallel work includes:

- SQLite schema, migrations, storage models, or data export/import changes.
- CLI command names, flags, output contracts, or README command examples.
- Source policy behavior, collectors, fetchers, or live-source rules.
- Shared configs under `config/`, GitHub workflows, Makefile targets, and AgentOps checks.
- `AGENTS.md`, `MEMORY.md`, `docs/issue-map.md`, `docs/verification.md`, `docs/architecture/banking-mvp.md`, and release checklists.

## File Ownership

Every issue should name:

- owned files or file families the agent may edit
- blocked files or file families the agent must not edit
- allowed shared docs, if a narrow reference update is required
- validation commands proving the touched surface

If two issues need the same shared file, merge the dependency first or rewrite the issues so one owns the shared edit and the other waits.

## Branches And Worktrees

- Branch names use `codex/issue-<number>-<short-slug>`.
- Worktree names use `.worktrees/issue-<number>-<short-slug>` when a nested worktree is needed.
- Start from latest `origin/main` only after dependencies have landed.
- If dependency work has not landed, stack intentionally on the dependency branch and target the dependency branch in the PR.
- Name the base PR or branch in the PR body for every stacked change.
- Do not carry uncommitted work from another branch into a new issue branch.

## Dependencies And Merge Order

- Merge prerequisite docs, schema, CLI, config, or workflow work before dependent product work.
- Demo readiness (#16) follows completed search work (#15).
- The opt-in public source pilot (#17) follows demo readiness and must stay disabled by default.
- Track A source work (#28-#34) and Track B data/intelligence work (#35-#43) should be rewritten or split before parallel implementation when they overlap schema, source policy, evidence, taxonomy, or scoring.
- AgentOps hygiene changes like #52 should merge before broad issue rewrites that rely on the new issue contract.

## Batch Verification

Before starting a batch:

- Verify issue and PR state from GitHub.
- Compare open PRs against `docs/issue-map.md` and `docs/agentops/current-work-batches.md`.
- Confirm owned and blocked files do not overlap.
- Run the narrow validation for each issue and the shared gate for the batch.

Before merging a batch, rerun `make agentops-pr`, `git diff --check`, and the product checks documented in `docs/verification.md` when product files changed.

Use these merge-gate states in PR reviews and batch reports:

- `Ready to review`: scope, metadata, docs, and local validation are complete.
- `Needs remediation`: implementation or validation is incomplete but unblocked.
- `Blocked by dependency`: prerequisite issue, PR, branch, or decision is not ready.
- `Blocked by conflict`: owned files, base branch, or merge order conflicts with active work.
- `Safe to merge after checks pass`: reviewer found no scope/metadata blocker, pending CI is the only remaining gate.

## Rollback

- Revert or close the smallest PR that introduced the bad operating change.
- If a shared doc created conflicts, restore the last merged source-of-truth section and reopen dependent issues with corrected ownership.
- If a check is too strict and blocks normal roadmap updates, relax the check in a small AgentOps PR rather than bypassing it.

## Stale Roadmap Context

When issue-map or roadmap context looks stale:

- Verify the current GitHub issue and PR state first.
- Update `docs/agentops/current-work-batches.md` from actual state, not old issue text.
- Keep `docs/issue-map.md` as the durable implementation sequence and add only compact current-work notes.
- Do not implement product behavior from stale batch examples without rechecking dependencies.

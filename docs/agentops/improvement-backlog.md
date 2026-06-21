# AgentOps Improvement Backlog

Track repeated agent defects and the guardrails selected to prevent them.

## Top priorities

| Priority | Issue | Evidence | Fix surface | Status |
|---:|---|---|---|---|
| P1 | Future source/scoring/alert validation can be mistaken for current required checks | Repo has planned modules documented before implementation | `docs/verification.md`, PR checklist | partially covered by workflow hygiene batch |

## Audit-derived backlog

| Priority | Failure pattern | Evidence type | Impact | Recommended system fix | Owner surface | Status |
|---:|---|---|---|---|---|---|
| P1 | Stale checkout or local branch confusion | Audit finding, terminal preflight notes, branch/worktree state | Agents may base fixes on old files, duplicate merged work, or open PRs from the wrong branch | Add a preflight that reports current branch, upstream, `origin/main` freshness, and dirty state before implementation | tooling | covered by this batch |
| P1 | Stale `docs/issue-map.md` statuses | Audit finding, issue/PR metadata mismatch | Agents may select completed, merged, or superseded issues and create unnecessary PRs | Add a small issue-map freshness check against open/closed issue and PR state, with stale rows reported as advisory failures | docs/tooling | covered by this batch; live checks remain optional |
| P1 | AgentOps runner or toolcache false-red | CI logs and audit finding | Agents may chase infrastructure noise as product regressions, wasting review time and risking unrelated edits | Document runner/toolcache failure signatures and add an AgentOps CI troubleshooting note that separates environment failures from test failures | CI/docs | covered by this batch; verify in Actions |
| P1 | Missing CI failure classification | Audit finding, repeated manual CI triage | Agents may change code before identifying whether the failure is product, AgentOps, dependency, runner, or flaky infrastructure | Add a required classification step to CI-fix prompts and a deterministic helper that labels common failure classes from logs | tooling | covered by this batch |
| P2 | Stacked PR merge-order confusion | PR dependency notes, concurrent worktree audit | Agents may merge or rebase follow-up work in the wrong order, causing conflicts or duplicated changes | Add dependency/merge-order fields to AgentOps PR guidance and require agents to name base PRs when work is stacked | prompt/manual | covered by this batch |
| P2 | Worktree accumulation | Preflight note: dirty nested worktree entries in main checkout | Agents may inspect stale worktrees, collide with another agent's files, or leave repo state hard to audit | Add an advisory worktree hygiene report that lists active worktrees, branches, dirty files, and age | tooling/docs | covered by this batch; cleanup remains manual |
| P2 | Missing next-issue workflow | Audit finding, prompt-library gap | Agents finishing a task lack a standard way to choose the next safe issue without broad repo spelunking | Add a next-issue prompt and recommender that uses issue-map status, dependencies, labels, scope, and owner-file constraints | prompt/tooling | covered by this batch; final task choice remains human-reviewed |
| P2 | Product CI vs AgentOps CI distinction is unclear | Audit finding, workflow naming ambiguity | Agents may apply product test expectations to AgentOps-only changes or ignore relevant AgentOps checks | Update verification and CI docs to explicitly separate product validation, AgentOps validation, and when each is required | docs/CI | covered by this batch |
| P2 | GitHub network errors misread as auth failures | Past thread audit | Agents may waste time rotating credentials or avoiding `gh` when the real issue is sandboxed network access | Add a GitHub/Codex runbook that separates auth, network approval, supported flags, and mutation safety | docs | covered by this batch |
| P2 | Generated Python cache artifacts recur in worktrees | Past thread audit | Agents may stage cache noise or leave dirty worktrees that obscure real changes | Add a generated-artifact check to workflow hygiene | tooling | covered by this batch |
| P2 | Prompt library regressions reintroduce workflow friction | Review agent finding | Agents may use compact prompts that skip required preflight/read-order steps | Add a prompt-library linter for required workflow prompts and implementation preflight markers | tooling/prompt | covered by this batch |
| P2 | PR template checks do not validate actual PR bodies | Review agent finding | A correct template can still produce PRs missing dependency, validation, or CI status evidence | Add an optional PR-body validator for local body files or live PRs | tooling | covered by this batch; live use remains explicit |
| P2 | Issue hygiene is documented but not checkable | Review agent finding | Issue rewrites can omit dependencies, owned files, validation, or stop conditions | Add a fixture/live issue-body checker plus local doc-contract validation | tooling/docs | covered by this batch; bulk issue rewriting remains future |

## Failure pattern template

### Pattern: <name>

Evidence:

- PR:
- Trace:
- Command output:

Fix:

- Selected surface:
- Files to update:
- Regression case:

Owner:
Status:

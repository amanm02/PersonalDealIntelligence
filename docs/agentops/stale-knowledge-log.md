# Stale Knowledge Log

Use this file to track guidance that may be outdated.

| Date | Source | Stale guidance | Replacement | Status |
|---|---|---|---|---|
| 2026-06-18 | RepoOS template runner docs | Repository-level runner wording | Organization-level `amanm02` runner available to `amanm02/PersonalDealIntelligence` | updated |
| 2026-06-21 | Agent audit notes | Local checkout or branch state can be assumed current | Run an implementation preflight that reports branch, upstream, `origin/main` freshness, dirty state, and optional issue/branch match before edits | covered by PR #56 |
| 2026-06-21 | Agent audit notes | `docs/issue-map.md` statuses can be treated as authoritative without GitHub freshness checks | Validate active issue-map rows against current issue/PR state before selecting or implementing work | covered by PR #56; live mode optional |
| 2026-06-21 | Agent audit notes | AgentOps runner or toolcache failures can be treated as product regressions | Classify AgentOps CI infrastructure failures separately from product test failures before changing code | covered by PR #56; verify in Actions |
| 2026-06-21 | Agent audit notes | Stacked AgentOps PRs can be reviewed as independent changes without merge-order context | Record base PR, dependency order, and owned-file boundaries in PR guidance for concurrent AgentOps work | covered by PR #56 |
| 2026-06-21 | Agent audit notes | Old worktrees can remain invisible during task setup | Report active worktrees, branch names, dirty state, merge status, issue mapping, and recommended cleanup action during AgentOps preflight | covered by PR #56; cleanup remains manual |
| 2026-06-21 | Agent audit notes | Agents need manual judgment to pick the next safe issue after finishing work | Use a next-issue workflow and helper that consider issue-map freshness, dependencies, scope, labels, and owner-file constraints | covered by PR #56; human selects final task |
| 2026-06-21 | Agent audit notes | CI logs can be debugged without first naming the failure class | Add a CI failure classifier covering product, AgentOps, dependency, runner/toolcache, and flaky infrastructure failures | covered by PR #56 |
| 2026-06-21 | Agent audit notes | Product CI and AgentOps CI can be treated as the same validation surface | Document which checks are product validation, which are AgentOps validation, and when each applies | covered by PR #56 |
| 2026-06-21 | Past workflow audit | GitHub CLI failures usually mean invalid auth | Separate sandbox/network approval failures from authentication failures before changing credentials or abandoning `gh` | covered by PR #56 |
| 2026-06-21 | Past workflow audit | Generated cache artifacts are harmless local noise | Treat tracked and untracked Python cache artifacts as workflow hygiene failures before review | covered by PR #56 |

## Rules

- Do not preserve stale guidance for historical reasons in active docs.
- Move historical context to decisions or retrospectives.
- Update or delete the lower-priority source when two sources conflict.

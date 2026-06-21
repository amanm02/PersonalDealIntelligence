# Current Work Batches

Last verified: 2026-06-21 from GitHub issue and PR state.

Use this file for near-term scheduling only. `docs/issue-map.md` remains the durable implementation sequence.

## Completed Prerequisites

| Work | State | Dependency status | Owned/blocked file families | Concurrent? | Validation gate | Merge order |
|---|---|---|---|---|---|---|
| #27 / PR #51 credit-card scope docs | merged | Closed and merged | Shared scope docs; blocks broad credit-card issue rewrites until reflected | done | Docs review and AgentOps checks | Already merged before #52 |
| Product CI / PR #50 | merged | Merged | `.github/workflows/ci.yml`; blocks PRs relying on product CI until merged | done | Product CI commands in `docs/verification.md` | Already merged before #52 |
| #15 / PR #53 banking find/search | merged | Closed and merged | CLI, README, tests; unblocks demo readiness | done | `python3 -m pytest` and search tests | Already merged before #16 |
| #52 / PR #55 concurrency operating model and hygiene checks | merged | Closed and merged | AgentOps concurrency docs, issue hygiene docs, prompt/PR template additions, and baseline hygiene scripts | done | `make workflow-hygiene`, `make agentops-pr`, `python3 -m pytest`, `git diff --check` | Already merged before PR #56 |
| #16 / PR #54 demo readiness implementation | merged | Verified complete; Issue #16 should close with this reconciliation | README, demo script, CLI/docs/tests; unblocks #17 after issue closure | done | Demo gate plus product CI commands | Already merged before #17 |
| PR #56 AgentOps optimization batch | merged | #52 / PR #55 and PR #54 verified merged | AgentOps docs, hygiene scripts, tests, PR template, workflow hygiene wiring, and AgentOps workflow remediation | done | `make workflow-hygiene`, `make agentops-pr`, `make agentops-test`, `python3 -m pytest`, `git diff --check` | Already merged before issue rewrites |

## Current Exclusive Work

| Work | State | Dependency status | Owned/blocked file families | Concurrent? | Validation gate | Merge order |
|---|---|---|---|---|---|---|
| #17 opt-in public source pilot | in progress on `codex/issue-017-public-source-pilot` | #16 is closed/completed; stale #17 blocked label removed during preflight | Source policy, public-pilot runtime, Banking CLI run/source commands, config, docs, tests. Blocks live-source expansion. | no; exclusive while this PR is open | Source policy validation, offline public-pilot tests, demo gate, product CI commands, no default live network | Merge before #28/#29/#31/#33 public-source expansion |

## Next Sequential Work

| Work | State | Dependency status | Owned/blocked file families | Concurrent? | Validation gate | Merge order |
|---|---|---|---|---|---|---|
| #28/#29/#31/#33 source expansion sequence | open; next only after #17 merges | Depends on #17 landing as the narrow disabled-by-default pilot | Source policy, collection rules, source health, freshness, managed coverage | no until #17 closes and issue bodies are rechecked | Source policy validation and offline tests; no default live network unless explicitly scoped | Start after #17 closes |

## Future Parallelizable Batches

| Batch | Issues | Dependency status | Owned/blocked file families | Concurrent? | Validation gate | Merge order |
|---|---|---|---|---|---|---|
| Source universe | #28, #29, #31, #33 | Open; several blocked or need rewrite | Source policy, collection rules, source health, freshness. Blocks collectors and live-source behavior outside explicit policy. | limited after rewrites split config from runtime | Source policy validation, collector tests, no default live network | #28 before #29/#31; #33 after #17 and source hardening |
| Taxonomy and persistence | #35, #36, #37, #39, #40, #42, #43 | Open; schema-heavy work needs exclusive scheduling | Migrations, models, query/service boundaries, export/import. Blocks CLI and scoring contract changes while active. | no for schema-adjacent PRs | Storage tests plus full pytest | Taxonomy and persistence foundations before rules, credit-card model, services, export |
| Evidence quality | #30, #32, #34, #41 | Open; some blocked or need rewrite | Evidence capture, official verification, QA benchmark, conflict audit. Blocks extractor/dedupe/scoring overlap. | limited after ownership split | Extractor, dedupe, QA, and conflict tests | Evidence capture before verification and conflict policy |
| Credit-card support | #27, #28, #36, #37, #40 | #27 complete; remaining issues open | Credit-card source scope, taxonomy, extraction fields, scoring. Blocks ad hoc credit-card runtime behavior elsewhere. | limited after source/taxonomy split | Product tests plus docs/safety review | Scope, source universe, taxonomy/rules, then model/scoring |
| Workflow hygiene / issue rewrites | Open issues labeled `needs-rewrite` | #52 and PR #56 are complete | Issue bodies, labels, templates, prompt library, current batches. Blocks implementation of stale broad issues. | yes if each rewrite owns separate issues and no shared docs | AgentOps checks and issue-body review | Rewrite stale issues before implementation |

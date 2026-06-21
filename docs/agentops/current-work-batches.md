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
| #16 / PR #54 demo readiness implementation | merged | Verified complete and reconciled | README, demo script, CLI/docs/tests; unblocks #17 after issue closure | done | Demo gate plus product CI commands | Already merged before #17 |
| PR #56 AgentOps optimization batch | merged | #52 / PR #55 and PR #54 verified merged | AgentOps docs, hygiene scripts, tests, PR template, workflow hygiene wiring, and AgentOps workflow remediation | done | `make workflow-hygiene`, `make agentops-pr`, `make agentops-test`, `python3 -m pytest`, `git diff --check` | Already merged before issue rewrites |
| #17 / PR #58 opt-in public source pilot | merged | Closed by PR #58 after #16 completed | Source policy, public-pilot runtime, Banking CLI run/source commands, config, docs, tests. Unblocks source-universe issue rewrites. | done | Source policy validation, offline public-pilot tests, demo gate, product CI commands, no default live network | Already merged before #28/#29/#31/#33 public-source expansion |
| #28A / PR #60 source-universe metadata | merged | Split from #28 and merged | Source metadata, trust tiers, official/source class flags, product coverage flags, safe seed placeholders, docs, tests. | done | Source policy validation, focused sources/CLI/collector tests, demo gate, full pytest, AgentOps checks | Already merged before #28B |
| #28B / PR #65 source onboarding workflow | merged | Split from #28 and merged; #64 closed | Source onboarding review helpers, filtered source listing, source show, onboarding-check, safe YAML scaffold, docs, tests. | done | Source policy validation, focused sources/CLI tests, demo gate, full pytest, AgentOps checks | Completes the current #28 source-universe/onboarding milestone |

## Current Exclusive Work

| Work | State | Dependency status | Owned/blocked file families | Concurrent? | Validation gate | Merge order |
|---|---|---|---|---|---|---|
| None known | Latest open-PR preflight returned no open PRs | Re-run GitHub preflight before starting new work | n/a | n/a | n/a |

## Next Sequential Work

| Work | State | Dependency status | Owned/blocked file families | Concurrent? | Validation gate | Merge order |
|---|---|---|---|---|---|---|
| #29/#30/#34 rewrite/split | open; preferred next step before implementation | #28A and #28B are merged; broad follow-up issue bodies still need narrowed contracts before coding | Issue bodies, labels, ownership, validation contracts, and demo-script planning only | read-only or docs/issue-only until narrowed implementation is selected | AgentOps checks and issue-body review; no product behavior change | Rewrite/split before #29A, #30A/#30B, or #34A implementation |

## Future Parallelizable Batches

| Batch | Issues | Dependency status | Owned/blocked file families | Concurrent? | Validation gate | Merge order |
|---|---|---|---|---|---|---|
| Source universe and live coverage | #29, #31, #33 | #28A/#28B complete; remaining issues are open and need narrow contracts before runtime expansion | Source policy, collection rules, source health, freshness. Blocks collectors and live-source behavior outside explicit policy. | limited after rewrites split config from runtime | Source policy validation, collector tests, no default live network | #29 before #31; #33 after #17 and source hardening |
| Taxonomy and persistence | #35, #36, #37, #39, #40, #42, #43 | Open; schema-heavy work needs exclusive scheduling | Migrations, models, query/service boundaries, export/import. Blocks CLI and scoring contract changes while active. | no for schema-adjacent PRs | Storage tests plus full pytest | Taxonomy and persistence foundations before rules, credit-card model, services, export |
| Evidence quality | #30, #32, #34, #41 | Open; some blocked or need rewrite | Evidence capture, official verification, QA benchmark, conflict audit. Blocks extractor/dedupe/scoring overlap. | limited after ownership split | Extractor, dedupe, QA, and conflict tests | Evidence capture before verification and conflict policy |
| Credit-card support | #27, #36, #37, #40 | #27 and #28 source scope complete; remaining issues open | Credit-card taxonomy, extraction fields, scoring, and rules. Blocks ad hoc credit-card runtime behavior elsewhere. | limited after taxonomy/rules split | Product tests plus docs/safety review | Scope, source universe, taxonomy/rules, then model/scoring |
| Workflow hygiene / issue rewrites | Open issues labeled `needs-rewrite` | #52 and PR #56 are complete | Issue bodies, labels, templates, prompt library, current batches. Blocks implementation of stale broad issues. | yes if each rewrite owns separate issues and no shared docs | AgentOps checks and issue-body review | Rewrite stale issues before implementation |

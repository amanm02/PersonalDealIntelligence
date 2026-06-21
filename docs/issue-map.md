# Issue Map

This document is the source of truth for the initial Banking MVP implementation order.

## Current product scope

Build the banking piece of Personal Deal Intelligence first.

Included:

- checking bonuses
- savings bonuses
- checking + savings bundle bonuses
- brokerage bonuses
- money market and CD bonuses
- publicly available business banking bonuses when clearly separated from personal offers
- personal and business credit card acquisition offers
- cash, points, miles, statement-credit, mixed, elevated limited-time, public issuer, and clearly marked targeted credit card offers from allowed non-private sources
- review/status workflow
- local digest
- local run history and dry-run orchestration
- offline demo readiness
- opt-in public-pilot source planning and guarded RSS collection

Deferred:

- clothing
- travel
- flights
- hotels
- cashback stack optimization
- browser extension
- full web dashboard
- live public source expansion beyond an explicit opt-in pilot
- credit card applications, form submission, or personalized financial advice
- full card number storage, private-session scraping, access-control bypass, CAPTCHA bypass, paywall bypass, and source-access workarounds

## Implementation sequence

The expanded MVP uses two coordinated tracks:

- **Track A: Research + Collection Engine** for source coverage, compliant collection, evidence, freshness, official verification, and QA.
- **Track B: Deal Intelligence + Database Layer** for persistence, taxonomy, rules, historical classification, rate handling, credit-card offer modeling, conflict handling, service/query boundaries, and export/import.

| Order | Issue | Title | Depends on | Status |
|---:|---|---|---|---|
| 00 | #1 | Bootstrap project operating layer and banking roadmap | none | closed |
| 01 | #2 | Define banking deal data model, storage, and migrations | #1 | closed |
| 02 | #3 | Build source registry and compliant source policy configuration | #1, optionally #2 | closed |
| 03 | #4 | Implement compliant collector framework for banking sources | #2, #3 | closed |
| 04 | #5 | Implement banking deal extraction from raw snapshots | #2, #4 | closed |
| 05 | #6 | Implement banking deal dedupe, canonicalization, and change tracking | #2, #5 | closed |
| 06 | #7 | Implement banking expected-value scoring engine | #2, #5, #6 | closed |
| 07 | #8 | Build review workflow CLI for banking deals | #2, #6, #7 | closed |
| 08 | #9 | Build banking deal alert digest and notification rules | #6, #7, #8 | closed |
| 09 | #10 | Add offline fixture smoke test for the full banking flow | #2-#9 | closed |
| 10 | #11 | Harden documentation, tests, and release checklist | #1-#10 | closed |
| 11 | #12 | Add local run history and dry-run command | #3, #4, #7, #9, #10, #11 | closed |
| 12 | #14 | Add realistic demo fixture corpus and source seed pack | #2, #3, #4, #5 | closed |
| 13 | #15 | Add product-facing banking deal find command | #2, #6, #7, #8, #14 | closed |
| 14 | #16 | Add fresh-clone demo readiness gate | #2-#12, #14, #15 | closed; PR #54 verified |
| 15 | #17 | Add opt-in compliant public source pilot | #3, #4, #10, #12, #16 | open |
| 16 | #18 | Sync issue map and roadmap after demo expansion | #1, after #14-#17 exist | closed |
| 17 | #27 | Expand MVP scope to include credit card offers | #1 | closed |
| 18 | #28 | Build comprehensive banking and credit card source universe with onboarding workflow | #3, #27 | open |
| 19 | #29 | Add compliant live fetcher hardening, retry rules, rate limits, and source health tracking | #3, #4, #28 | open |
| 20 | #30 | Add evidence capture with raw snapshots, content hashes, and source-term links | #2, #4, #5, #29 if live metadata is reused | open |
| 21 | #31 | Add freshness scheduling, stale-source detection, and recrawl priority rules | #3, #12, #28, #29 | open |
| 22 | #32 | Add official-source verification workflow for third-party deal discoveries | #6, #28, #30 | open |
| 23 | #33 | Expand public source pilot into managed source coverage library | #17, #28, #29, #31, #32 | open |
| 24 | #34 | Add research QA benchmark for missed, stale, duplicate, and incorrectly extracted deals | #5, #6, #7, #10, #14, #40 if available | open |
| 25 | #35 | Add explicit candidate, source-link, score, and run-history persistence tables | #2, #5, #6, #7, #12 | open |
| 26 | #36 | Add canonical financial product taxonomy and offer lifecycle state machine | #2, #6, #27 | open |
| 27 | #37 | Add eligibility and requirements rules engine for banking and credit card offers | #5, #35, #36 | open |
| 28 | #38 | Add historical offer tracking and best-ever/typical/weak classification | #6, #35, #36, #40 for credit cards | open |
| 29 | #39 | Add APY and rate normalization for savings, money market, and CD offers | #2, #5, #7, #37 | open |
| 30 | #40 | Add credit card offer model, extraction fields, and scoring framework | #2, #5, #6, #7, #27, #36, #37 where possible | open |
| 31 | #41 | Add conflict resolution policy and reviewer override audit log | #6, #30, #32, #35, #40 | open |
| 32 | #42 | Add query and service layer for future dashboard/API consumption | #2, #6, #7, #8, #35, #36 | open |
| 33 | #43 | Add data export, import, backup, and restore workflow | #2, #35, #41 if available | open |

## Current work and concurrency

Current GitHub state should be verified before editing because batch examples in issue bodies can become stale.

- Completed prerequisites: #27 / PR #51, product CI / PR #50, #15 / PR #53, #52 / PR #55, PR #54 demo readiness, and PR #56 AgentOps workflow hygiene are merged.
- Current exclusive work: none known from the latest open-PR preflight.
- Next sequential work: #17 opt-in public source pilot after #16 is closed by the demo readiness reconciliation PR.
- Future work #28-#43 should be split or rewritten before implementation when it overlaps source policy, schema, taxonomy, evidence, scoring, CLI, workflow, or shared docs.
- Use `docs/agentops/concurrency.md`, `docs/agentops/issue-hygiene.md`, and `docs/agentops/current-work-batches.md` before launching parallel agents.

## Dependency notes

- #1 should be completed first because it establishes the repo operating layer.
- #2 and #3 can proceed after #1, but #4 needs both storage and source policy concepts.
- #5 requires raw snapshot inputs from #4 and storage from #2.
- #6 should not run before extraction exists because dedupe needs candidates.
- #7 should not run before canonical deal data exists.
- #8 makes the project usable locally before alert digests.
- #9 depends on scoring and status because the digest needs priorities and user workflow state.
- #10 proves the whole MVP flow with local fixtures only.
- #11 hardens the MVP after the flow exists.
- #12 adds repeated-run support after the core flow is stable.
- GitHub number #13 is a merged pull request, not a Banking MVP issue.
- #14 adds a reusable offline demo corpus and source seed pack before product-facing search.
- #15 adds a local find/search command on top of canonical deals, scoring, review CLI, and demo data.
- #16 defines the fresh-clone demo readiness gate after the core flow and demo search exist.
- #17 is a separate opt-in public source pilot after offline demo readiness; it must stay disabled by default and source-policy controlled.
- #18 keeps this roadmap aligned with the current GitHub issue sequence.
- #27 is documentation-only scope alignment. It does not add runtime credit-card collection, extraction, scoring, or review behavior.
- #28-#34 form Track A and Track A+B work for source coverage, compliant fetch hardening, evidence capture, freshness, official verification, managed source expansion, and QA.
- #35-#43 form Track B work for persistence, taxonomy, rules, historical classification, rate handling, first-class credit-card offer support, conflict/audit handling, query/service access, and export/import.
- Credit-card support should be implemented through the dedicated Track A/B issues, especially #28, #36, #37, and #40, not crammed into existing deposit-only components without tests and docs.

## Implementation principles

- Prefer local fixtures before live sources.
- Keep source collection policy-driven.
- Preserve evidence for extracted terms.
- Keep scoring transparent and configurable.
- Treat ambiguous extraction as `unknown`, not guessed.
- Keep tests offline by default.
- Do not add non-MVP deferred categories during the Banking MVP.
- Keep credit-card acquisition offer ranking transparent and evidence-backed; do not automate applications or present personalized financial advice.

## Suggested PR shape

Use one PR per issue unless the change is docs-only and explicitly grouped.

Recommended branch naming:

```text
codex/issue-001-bootstrap-banking-docs
codex/issue-002-banking-data-model
codex/issue-003-source-policy
```

## Done definition

An issue is done when:

- acceptance criteria are satisfied
- docs are updated where behavior changed
- validation from `docs/verification.md` was run or explicitly explained
- safety/compliance boundaries are preserved
- final response includes Summary, Files changed, Validation, and Risks / follow-ups

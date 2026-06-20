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
- review/status workflow
- local digest

Deferred:

- clothing
- travel
- flights
- hotels
- cashback stack optimization
- browser extension
- full web dashboard
- run history and dry-run orchestration

## Implementation sequence

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
| 10 | #11 | Harden documentation, tests, and release checklist | #1-#10 | in review |
| 11 | #12 | Add local run history and dry-run command | #3, #4, #7, #9, #10, #11 | open |

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

## Implementation principles

- Prefer local fixtures before live sources.
- Keep source collection policy-driven.
- Preserve evidence for extracted terms.
- Keep scoring transparent and configurable.
- Treat ambiguous extraction as `unknown`, not guessed.
- Keep tests offline by default.
- Do not add deferred categories during the Banking MVP.

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

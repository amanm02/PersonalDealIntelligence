# Agent Instructions

This repository builds Personal Deal Intelligence. The initial build is the **Banking MVP only**.

These instructions apply to Codex and other coding agents working in this repo.

## Read order

Before implementing a GitHub issue, read in this order:

1. `AGENTS.md`
2. `docs/issue-map.md`
3. `docs/verification.md`
4. `docs/architecture/banking-mvp.md`
5. `docs/decisions.md`
6. The GitHub issue body
7. Any linked implementation plan
8. Only the files needed for the task

Do not read unrelated docs or expand scope unless the issue requires it.

## Scope

The current scope is banking promotion intelligence:

- checking account bonuses
- savings account bonuses
- checking + savings bundle bonuses
- brokerage bonuses
- money market and CD bonuses
- credit card sign-up bonuses only as a deferred banking-adjacent extension

Out of scope for the initial build:

- clothing deals
- travel deals
- flights
- hotels
- cashback stack optimization
- browser extensions
- automatic financial actions

## Safety and compliance rules

Do not implement:

- bot-protection evasion
- CAPTCHA bypassing
- IP proxy rotation to bypass access controls
- logged-in banking portal scraping
- credential collection
- account opening automation
- money movement automation
- storage of SSNs, account numbers, government IDs, banking passwords, or session cookies

Collection must be policy-driven. Source behavior should be configured in machine-readable source policy files before collector code uses the source.

Prefer these input methods:

1. local fixtures
2. manual text
3. user-provided URL records
4. RSS feeds
5. email exports or user-authorized parsed content
6. official APIs or affiliate feeds when allowed
7. explicitly permitted public pages with low-frequency checks

Tests must not make live network calls unless an issue explicitly adds an integration test that is disabled by default.

## Implementation style

Use the smallest safe change that satisfies the issue acceptance criteria.

Default preferences unless existing repo conventions differ:

- Python
- SQLite for local-first storage
- deterministic tests
- local fixtures
- explicit config files
- clear domain models
- transparent scoring, not black-box logic

Do not add a large framework unless the issue requires it.

## Documentation expectations

When changing behavior, update the relevant docs:

- `README.md` for setup and user-facing commands
- `docs/issue-map.md` for issue status or dependency changes
- `docs/verification.md` for validation commands
- `docs/architecture/banking-mvp.md` for architectural changes
- `docs/decisions.md` for material decisions

Keep docs concise. Prefer source-of-truth pointers over long duplicated context.

## Validation expectations

Use `docs/verification.md` as the source of truth.

For code changes, run the most specific tests first, then broader validation if available.

For docs-only changes, manually review:

- markdown structure
- internal links
- scope alignment
- no unsafe implementation instructions
- no claims that unbuilt commands already work

## Final response format

Every Codex final response must include:

```text
Summary
Files changed
Validation
Risks / follow-ups
```

Include exact validation commands and results. If validation could not be run, explain why.

## Issue discipline

- Do not expand beyond the issue.
- Do not mix unrelated issues in one PR.
- Do not implement deferred categories.
- Do not silently change public behavior without tests or docs.
- Preserve raw evidence when extracting banking terms.
- Mark ambiguous terms as unknown rather than guessing.

# Decision Log

This document records material project decisions for Personal Deal Intelligence.

## DEC-001: Banking is the first MVP category

Date: 2026-06-17

Decision: Build the banking promotion tracker first.

Rationale:

- Banking promotions are easier to structure than flights or clothing deals.
- Expected dollar value per useful alert is high.
- The data model has clear fields such as bonus amount, direct deposit requirement, minimum balance, monthly fee, and expiration date.
- A banking MVP establishes reusable ingestion, extraction, scoring, review, and digest layers for future categories.

Consequences:

- Clothing, travel, flights, hotels, and cashback stack optimization are deferred.
- Initial docs and issues should remain banking-specific.

## DEC-002: Local-first personal-use architecture

Date: 2026-06-17

Decision: Use a local-first architecture for the initial build.

Rationale:

- The project is for personal use.
- Local SQLite and local artifacts reduce infrastructure overhead.
- Local-first design limits sensitive data exposure.
- The first MVP does not require hosted services.

Consequences:

- Prefer SQLite for storage.
- Prefer CLI and local markdown digest before a web app.
- Use local fixtures for early validation.

## DEC-003: Policy-driven source collection

Date: 2026-06-17

Decision: Every source must have explicit policy configuration before collection behavior is implemented.

Rationale:

- Deal discovery can drift into brittle or unsafe scraping if source rules are implicit.
- Source policies make collection method, frequency, and compliance notes visible.
- Codex needs explicit constraints to avoid adding unsafe behavior.

Consequences:

- Add source registry before collector implementation.
- Tests should verify unsafe source configs are blocked.
- Collection should be disabled by default unless explicitly allowed.

## DEC-004: Conservative source access and privacy boundaries

Date: 2026-06-17

Decision: The project must keep source collection policy-driven, avoid private-session collection, keep financial actions under user control, and keep private auth material and highly sensitive personal identifiers out of project storage.

Rationale:

- Aggressive or implicit source access increases legal, security, maintenance, and account-risk exposure.
- Banking sources are sensitive and should be handled conservatively.
- The project can still be useful through fixtures, manual URLs, RSS, email exports, APIs, and compliant public pages.

Consequences:

- AGENTS.md and docs must continue to enforce this boundary.
- Future collectors must fail closed on unsafe source policies.

## DEC-005: Evidence-first extraction

Date: 2026-06-17

Decision: Extracted banking terms should preserve evidence spans or source references when possible.

Rationale:

- Banking promotion terms are high-impact and often nuanced.
- The user should verify final terms on the official institution page.
- Ambiguous extraction should not be silently converted into false confidence.

Consequences:

- Extractor output should include evidence and missing fields.
- Scoring should penalize missing or low-confidence high-impact terms.
- Review workflow should surface conflicts and missing data.

## DEC-006: Transparent scoring over black-box ranking

Date: 2026-06-17

Decision: Banking deal scoring must expose component-level estimates.

Rationale:

- A single score without explanation is not useful for financial decision support.
- Banking deal value depends on fees, cash lockup, direct deposit friction, eligibility, and uncertainty.
- Configurable assumptions make the system easier to tune for personal preferences.

Consequences:

- Scoring output should include gross value, fee cost, cash lockup cost, friction/risk penalties, net value, and explanation.
- Scoring config should be versioned and documented.

## DEC-007: Offline fixture pipeline before live sources

Date: 2026-06-17

Decision: Build an offline fixture smoke test before adding real source execution.

Rationale:

- The MVP pipeline should be testable without network access.
- Fixtures help validate extraction, dedupe, scoring, digest, and CLI behavior deterministically.
- This prevents source integration complexity from hiding core product issues.

Consequences:

- Issues should prioritize local fixtures before live collection.
- Tests should remain offline by default.

## DEC-008: CLI before dashboard

Date: 2026-06-17

Decision: Use a CLI review workflow before building a dashboard.

Rationale:

- CLI is faster to implement and easier to test.
- The project needs data correctness before UI polish.
- A CLI still supports the core personal workflow: list, inspect, filter, update status, and generate digest.

Consequences:

- Dashboard work is deferred.
- CLI command docs should be updated as implementation stabilizes.

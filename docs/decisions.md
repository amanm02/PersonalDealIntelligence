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

## DEC-009: Use stdlib sqlite3 and versioned SQL migrations for storage

Date: 2026-06-17

Decision: Implement the initial Banking MVP storage layer with Python stdlib
`sqlite3`, SQLite, and package-owned versioned SQL migration files.

Rationale:

- The repo did not have an existing runtime stack or ORM convention.
- Issue #2 needs the smallest safe local-first storage foundation.
- SQL migration files keep schema changes explicit and reviewable.

Consequences:

- The first storage helpers stay lightweight and dictionary-based.
- Unknown extracted banking terms are stored as `NULL` rather than guessed.
- A larger ORM can be reconsidered only if later issues create enough model
  complexity to justify it.

## DEC-010: Keep source policy config-first with YAML

Date: 2026-06-17

Decision: Use `config/banking_sources.yaml` and a small `pdi.sources` validator
as the source policy authority before collectors are implemented.

Rationale:

- Issue #3 needs explicit, machine-readable source rules before live collection.
- YAML keeps placeholder source records readable for manual review.
- Keeping policy separate from SQLite avoids a migration before collectors need
  persisted source policy state.

Consequences:

- `PyYAML` is a runtime dependency.
- Future collectors must load and enforce `pdi.sources` policies before any
  source access.
- SQLite `source_records` remain snapshot provenance until a later issue
  requires full source-policy persistence.

## DEC-011: Keep initial collectors offline-first

Date: 2026-06-17

Decision: Implement the first collector framework with local/manual fixture
collectors and policy-gated interfaces, but no built-in live network client.

Rationale:

- Issue #4 needs raw snapshot flow without introducing unsafe scraping behavior.
- Local fixtures keep collector tests deterministic and offline.
- Explicit injected fetchers give future issues an integration point while
  preserving source-policy enforcement before any fetch-like behavior.

Consequences:

- Manual text, manual URL records, RSS/Atom fixtures, email export text, and API
  fixture payloads can produce `CollectedSnapshot` records.
- HTML fetching remains opt-in for future work and is blocked unless source
  policy allows approved, non-login, low-frequency scraping.
- No proxy, CAPTCHA bypass, browser automation, credentials, or private-session
  collection behavior is introduced.

## DEC-012: Store extracted candidates separately from canonical deals

Date: 2026-06-17

Decision: Store Issue #5 extractor output in `banking_deal_candidates` rather
than writing directly to canonical `banking_deals`.

Rationale:

- Extraction is intentionally imperfect and pre-dedupe.
- Canonical deal creation, merge decisions, conflicts, and change tracking belong
  to the later dedupe/canonicalization layer.
- Candidate rows can preserve raw snapshot links, evidence spans, missing fields,
  confidence, and rejection state without implying a reviewed canonical deal.

Consequences:

- Issue #5 can persist extraction results without overwriting canonical records.
- Issue #6 should consume candidate rows and decide when to create or update
  canonical `banking_deals`.

## DEC-013: Use conservative canonicalization with source evidence links

Date: 2026-06-17

Decision: Dedupe should convert extracted candidates into canonical banking
deals using conservative exact, same-source/product, and strong fuzzy matching,
while preserving every candidate/source reference in explicit source-link rows.

Rationale:

- Banking promotion terms can differ across official pages, blogs, feeds, and
  newsletters.
- False merges would make scoring and review less trustworthy than duplicate
  records.
- Source links and change events keep conflicting evidence reviewable.

Consequences:

- Low-confidence candidates do not fuzzy-merge.
- Official-source evidence is preferred when source authority is known.
- Important conflicts create change events and mark canonical deals
  `needs_review`.

## DEC-014: Keep scoring transparent and config-driven

Date: 2026-06-18

Decision: Implement Banking MVP scoring as a deterministic, component-level
engine backed by `config/banking_scoring.yaml`.

Rationale:

- Banking bonus value depends on configurable personal assumptions such as
  opportunity cost, fee exposure, direct-deposit friction, restrictions, and
  tolerance for missing terms.
- Review decisions are easier to trust when the gross bonus, costs, penalties,
  net value, score, action, explanation, and missing-data warnings are visible.
- Scoring should rank deals for personal review without presenting outputs as
  financial advice.

Consequences:

- Callers can use `pdi.scoring` to score canonical deals and optionally persist
  the existing `estimated_net_value_cents` field.
- Config changes must be validated and covered by offline tests.
- Alert delivery remains a separate later issue.

## DEC-015: Use argparse CLI for local banking review

Date: 2026-06-18

Decision: Implement the first review workflow as an `argparse` CLI exposed
through `pdi banking` and `python -m pdi`.

Rationale:

- The repo already uses small stdlib command modules and has no web framework.
- A CLI is enough for local inspection, filtering, scoring, and status updates.
- Table output is readable for manual review, while JSON output keeps tests and
  later automation deterministic.

Consequences:

- The default local database path is `data/pdi.sqlite`, with `--db` available
  for fixture and alternate databases.
- Status changes are recorded as local review events and do not trigger any
  financial action.
- `in_progress` is the preferred active-review status; existing `applied` rows
  remain accepted for compatibility.

## DEC-016: Generate local alert digests before external notifications

Date: 2026-06-18

Decision: Implement Banking MVP alerts as local markdown and JSON digest
artifacts backed by `config/banking_alerts.yaml`, with external notification
channels disabled by default and limited to no-op/dry-run behavior.

Rationale:

- The first alert surface should reduce manual checking without creating
  delivery, privacy, or credential risk.
- Markdown is easy to read locally, while JSON keeps tests deterministic and
  leaves room for later automation.
- Disabled notification hooks make future delivery channels explicit without
  sending live messages during the Banking MVP.

Consequences:

- `pdi.alerts` owns alert config validation, digest sectioning, and rendering.
- `pdi banking digest` writes local artifacts only.
- Any future live email, webhook, or messaging provider must add explicit
  configuration, dry-run tests, environment-variable handling, and safety review.

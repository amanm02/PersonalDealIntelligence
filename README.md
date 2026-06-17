# Personal Deal Intelligence

Personal Deal Intelligence is a local-first personal research system for discovering, structuring, scoring, and reviewing high-value deals.

The initial build is scoped to **banking promotions only**. Other deal categories such as clothing, travel, flights, hotels, and general shopping are intentionally deferred until the Banking MVP is stable.

## Banking MVP scope

The Banking MVP tracks and evaluates banking-related promotions, including:

- checking account bonuses
- savings account bonuses
- checking + savings bundle bonuses
- brokerage deposit or transfer bonuses
- money market and CD bonuses
- credit card sign-up bonuses as a deferred banking-adjacent extension

The system should help answer:

- What new banking promotions are worth reviewing?
- What is the estimated net value after fees, cash lockup, friction, and uncertainty?
- Which deals are expiring soon?
- Which deals have conflicting or missing terms?
- Which deals have I already reviewed, skipped, applied for, or completed?

## Non-goals

The initial build must not include:

- clothing deal tracking
- travel deal tracking
- flight search
- hotel search
- cashback stack optimization
- browser extension work
- automated financial actions, applications, enrollment, or money movement
- collection of private auth material
- collection or storage of highly sensitive personal identifiers
- source access workarounds or private-session collection

## Safety and compliance boundaries

This project is for personal organization and research. It must not be treated as financial advice.

Implementation rules:

- Use APIs, RSS feeds, email exports, manual text, and explicit source policies before any web collection.
- Respect each source's terms, robots policy, rate limits, and collection method.
- Keep private auth material and highly sensitive personal identifiers out of project storage.
- Keep all financial actions, applications, enrollment, and money movement under direct user control.
- Preserve evidence for extracted terms so the user can verify the final offer on the official institution page.
- Unknown or ambiguous terms should remain unknown rather than being guessed.

## Initial architecture

The Banking MVP is organized around these layers:

1. **Source registry** — machine-readable source policies and collection rules.
2. **Collector framework** — compliant source intake from manual text, RSS fixtures, email exports, APIs, or explicitly allowed pages.
3. **Raw snapshots** — stored source text and metadata.
4. **Extractor** — banking-specific parsing into structured deal candidates.
5. **Dedupe and canonicalization** — merge repeated mentions while preserving evidence and conflicts.
6. **Scoring** — estimate net value and explain score components.
7. **Review workflow** — CLI-based status tracking and inspection.
8. **Digest** — local markdown/JSON summaries for high-value, expiring, changed, or review-needed deals.
9. **Run history** — local repeated-run tracking with dry-run support.

See `docs/architecture/banking-mvp.md` for details.

## Planned issue sequence

The initial Banking MVP is tracked through these GitHub issues:

1. Banking MVP 00: Bootstrap project operating layer and banking roadmap
2. Banking MVP 01: Define banking deal data model, storage, and migrations
3. Banking MVP 02: Build source registry and compliant source policy configuration
4. Banking MVP 03: Implement compliant collector framework for banking sources
5. Banking MVP 04: Implement banking deal extraction from raw snapshots
6. Banking MVP 05: Implement banking deal dedupe, canonicalization, and change tracking
7. Banking MVP 06: Implement banking expected-value scoring engine
8. Banking MVP 07: Build review workflow CLI for banking deals
9. Banking MVP 08: Build banking deal alert digest and notification rules
10. Banking MVP 09: Add offline fixture smoke test for the full banking flow
11. Banking MVP 10: Harden documentation, tests, and release checklist
12. Banking MVP 11: Add local run history and dry-run command

See `docs/issue-map.md` for dependencies and implementation order.

## Local setup

The current runtime foundation is a minimal Python package with SQLite storage
for Banking MVP deal data. It uses stdlib `sqlite3` and versioned SQL
migrations under `src/pdi/storage/migrations/`.

Install for local development:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

Initialize a local database with fictional mock banking deals:

```bash
python3 -m pdi.storage init --db data/pdi.sqlite --seed-fixture examples/banking_deals.json
```

Run tests:

```bash
python3 -m pytest
```

Future Banking MVP commands:

```bash
pdi banking list
pdi banking show <deal_id>
pdi banking update-status <deal_id> <status>
pdi banking review-needed
pdi banking expiring --days 14
pdi banking run --dry-run
pdi banking runs
```

These are target commands. Codex should adjust them only if the implementation chooses a different CLI convention and updates the docs consistently.

## Validation

Use `docs/verification.md` as the source of truth for validation.

For storage changes, run:

```bash
python3 -m pytest tests/storage
python3 -m pytest
python3 -m pdi.storage init --db /tmp/pdi-issue2.sqlite --seed-fixture examples/banking_deals.json
```

Documentation-only changes should be manually checked for:

- clear Banking MVP scope
- accurate internal links
- no claims that unbuilt commands already work
- no instructions to circumvent source rules or collect private-session data
- concise Codex-readable structure

## Repository docs

- `AGENTS.md` — instructions for Codex and future coding agents
- `docs/issue-map.md` — ordered Banking MVP implementation map
- `docs/verification.md` — validation commands and expectations
- `docs/architecture/banking-mvp.md` — system architecture
- `docs/decisions.md` — decision log
- `docs/prompt-library.md` — reusable Codex prompts
- `docs/release-checklists/banking-mvp.md` — first release checklist

## Current status

Initial documentation and issue planning are in progress. The Banking MVP now has
a local SQLite storage foundation for raw snapshots, canonical deals, structured
terms, and status/change history.

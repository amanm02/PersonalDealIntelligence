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
- publicly available business banking bonuses when clearly separated from personal offers
- personal and business credit card acquisition offers, including cash, points, miles, statement-credit, mixed, elevated limited-time, public issuer, and clearly marked targeted offers from allowed non-private sources

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
- credit card applications or form submission
- collection of private auth material
- collection or storage of full card numbers, highly sensitive personal identifiers, or sensitive personal financial information
- source access workarounds or private-session collection
- bypassing anti-bot protections, paywalls, CAPTCHAs, or access controls

## Safety and compliance boundaries

This project is for personal organization and research. It must not be treated as financial advice.

Implementation rules:

- Use APIs, RSS feeds, email exports, manual text, and explicit source policies before any web collection.
- Respect each source's terms, robots policy, rate limits, and collection method.
- Keep private auth material and highly sensitive personal identifiers out of project storage.
- Keep all financial actions, applications, enrollment, and money movement under direct user control.
- Preserve evidence for extracted terms so the user can verify the final offer on the official institution or issuer page.
- Treat issuer application restrictions as review notes, not personalized financial advice.
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

The active Banking MVP issue sequence is tracked in `docs/issue-map.md`.
The current roadmap continues past the core flow into offline demo readiness and credit-card acquisition support:

- #14 realistic demo fixture corpus and source seed pack
- #15 product-facing banking deal find/search command
- #16 fresh-clone demo readiness gate
- #17 opt-in compliant public source pilot, kept separate from the offline demo
- #18 roadmap synchronization after the demo expansion
- #27 credit-card acquisition scope alignment
- #28-#34 Track A research, collection, evidence, verification, freshness, and QA work
- #35-#43 Track B deal intelligence, taxonomy, rules, credit-card model, conflict, service, and export work

Commands for #14-#17 behavior should stay documented as planned or expected
until the corresponding issue implements and validates them.

Post-MVP and deferred ideas live under `docs/roadmap/` so they do not pollute the active MVP scope:

- `docs/roadmap/future-features.md`
- `docs/roadmap/future-categories.md`
- `docs/roadmap/banking-v2.md`
- `docs/roadmap/ideas-parking-lot.md`

## Local setup

The current runtime foundation is a minimal Python package with SQLite storage
for Banking MVP deal data, a YAML-backed source policy registry, an
offline-first collector framework, a deterministic banking extractor,
conservative dedupe, transparent expected-value scoring, and a local review
CLI with local alert digest generation, an offline fixture smoke flow, and
local run history/dry-run orchestration.
Storage uses stdlib `sqlite3` and versioned SQL migrations under
`src/pdi/storage/migrations/`.

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

Validate banking source policies:

```bash
python3 -m pdi.sources validate --config config/banking_sources.yaml
```

Validate the reusable offline demo source pack:

```bash
python3 -m pdi.sources validate --config config/banking_sources.demo.yaml
```

`config/banking_sources.yaml` is the source-policy authority for future
collectors. Add new sources there only after documenting the collection method,
banking category/subcategory scope, rate limits, terms/robots notes, compliance
status, and review date. Leave sources disabled unless they are explicitly
approved, and never add credentials, private tokens, personal mailbox labels, or
private-session collection details.

`config/banking_sources.demo.yaml` and `examples/demo_banking/` provide a
fictional, reusable, local-only demo source seed pack. It includes official-page
style text, RSS/deal-blog fixture content, newsletter export text, manual pasted
notes, duplicate/conflicting mentions, low-value and expired offers, ambiguous
terms, and non-deal content. The demo pack does not fetch websites, use browser
automation, connect email accounts, send notifications, or perform banking
actions.

Collector support exists under `pdi.collectors` for manual text, manual URL
records, RSS/Atom fixture content, newsletter/email export text, and
fixture-backed API payloads. Collectors normalize raw content into snapshot
records that can be persisted to `raw_deal_snapshots`. HTML fetching has no
built-in live network client and is blocked unless an enabled, approved source
policy explicitly allows non-login scraping and frequency metadata permits the
attempt.

Extractor support exists under `pdi.extractors` for offline, rule-based parsing
of raw banking snapshot text into `banking_deal_candidates`. Extracted
candidates preserve evidence spans, missing fields, confidence, and notes, but
do not directly create or update canonical `banking_deals`.

Dedupe support exists under `pdi.dedupe` for conservative canonicalization of
non-rejected candidates. It creates or updates canonical banking deals, preserves
candidate/source evidence in `banking_deal_source_links`, records material
differences in `deal_change_events`, and marks important conflicts
`needs_review`.

Scoring support exists under `pdi.scoring` for canonical banking deals. It reads
`config/banking_scoring.yaml`, returns component-level estimates for gross
bonus, fees, cash lockup, hassle, risk/unclear terms, net value, score band,
recommended action, explanation, and missing-data warnings. Scores are for
personal review only and are not financial advice.

Validate banking scoring assumptions:

```bash
python3 -m pdi.scoring validate --config config/banking_scoring.yaml
```

Alert digest support exists under `pdi.alerts` for local markdown and JSON
summaries of high-value, expiring, changed, watched, or review-needed banking
deals. It reads `config/banking_alerts.yaml`. External notification channels are
disabled by default and currently use no-op/dry-run behavior only.

Validate banking alert rules:

```bash
python3 -m pdi.alerts validate --config config/banking_alerts.yaml
```

Review stored banking deals locally:

```bash
python3 -m pdi --db data/pdi.sqlite banking list
python3 -m pdi --db data/pdi.sqlite banking show <deal_id>
python3 -m pdi --db data/pdi.sqlite banking update-status <deal_id> in_progress --note "Reviewing official page."
python3 -m pdi --db data/pdi.sqlite banking review-needed
python3 -m pdi --db data/pdi.sqlite banking expiring --days 14
python3 -m pdi --db data/pdi.sqlite banking search --institution "Example Bank"
python3 -m pdi --db data/pdi.sqlite banking score <deal_id>
python3 -m pdi --db data/pdi.sqlite banking digest
python3 -m pdi --db data/pdi.sqlite banking digest --format json --output data/digests/banking_digest.json
```

Use `--format json` on review commands when structured output is needed.
Status changes are local review notes only. The system does not perform account
or card applications, enrollment, money movement, form submission, or other
financial actions. Verify final offer terms on the official institution or
issuer page before acting.
Use digest output as a local review aid only; generated digest artifacts should
not contain credentials or highly sensitive personal identifiers.

Run the full offline Banking MVP smoke flow with synthetic fixtures only:

```bash
python3 -m pdi --db /tmp/pdi-banking-smoke.sqlite banking smoke-test \
  --digest-output /tmp/pdi-banking-smoke-digest.md \
  --as-of 2026-06-18 \
  --reset-db
```

Use `--format json` when a structured smoke summary is needed. The smoke command
loads local fixture text, creates raw snapshots, extracts candidates,
canonicalizes duplicate/conflicting deals, scores canonical deals, writes a
local markdown digest, and prints summary counts. It does not fetch websites,
connect email accounts, send external messages, or automate banking actions.

Run tests:

```bash
python3 -m pytest
```

Run the local Banking MVP workflow once with run history:

```bash
python3 -m pdi --db data/pdi.sqlite banking run
python3 -m pdi --db data/pdi.sqlite banking run --dry-run
python3 -m pdi --db data/pdi.sqlite banking run --execute
python3 -m pdi --db data/pdi.sqlite banking runs --limit 10
python3 -m pdi --db data/pdi.sqlite banking run-status <run_id>
```

The run command defaults to dry-run mode. Dry-run records run history in the
real database but runs the workflow against a temporary database copy, does not
write the durable digest artifact, and records the requested digest path only
as metadata. Use `--execute` only when you want to persist workflow changes and
write the digest artifact.

For optional local scheduling, call the explicit execute command from cron or
launchd and redirect output to a local log file. Do not add cloud schedulers,
credentialed source access, browser automation, or automatic banking actions as
part of local scheduling. Stale run-lock cleanup is not automatic yet; if a
process is interrupted while running, inspect `banking_run_locks` manually and
remove a stale local lock only after confirming no run is active.

Planned demo-readiness work will add or document fixture-backed commands for
finding ranked local banking deals and running a fresh-clone demo gate. Until
#15 and #16 are implemented, those commands are roadmap items, not current CLI
guarantees.

## Validation

Use `docs/verification.md` as the source of truth for validation.

For storage changes, run:

```bash
python3 -m pytest tests/storage
python3 -m pytest
python3 -m pdi.storage init --db /tmp/pdi-issue2.sqlite --seed-fixture examples/banking_deals.json
```

For source policy changes, run:

```bash
python3 -m pdi.sources validate --config config/banking_sources.yaml
python3 -m pytest tests/sources
python3 -m pytest
```

For collector changes, run:

```bash
python3 -m pytest tests/collectors
python3 -m pytest tests/sources
python3 -m pytest tests/storage
python3 -m pytest
```

For extractor changes, run:

```bash
python3 -m pytest tests/extractors
python3 -m pytest tests/storage
python3 -m pytest
```

For dedupe changes, run:

```bash
python3 -m pytest tests/dedupe
python3 -m pytest tests/storage
python3 -m pytest tests/extractors
python3 -m pytest
```

For scoring changes, run:

```bash
python3 -m pdi.scoring validate --config config/banking_scoring.yaml
python3 -m pytest tests/scoring
python3 -m pytest tests/dedupe
python3 -m pytest tests/storage
python3 -m pytest
```

For review CLI changes, run:

```bash
python3 -m pytest tests/cli
python3 -m pytest tests/storage
python3 -m pytest tests/scoring
python3 -m pytest
```

For alert digest changes, run:

```bash
python3 -m pdi.alerts validate --config config/banking_alerts.yaml
python3 -m pytest tests/alerts
python3 -m pytest tests/cli
python3 -m pytest tests/scoring
python3 -m pytest
```

For offline smoke flow changes, run:

```bash
python3 -m pytest tests/integration
python3 -m pytest tests/cli
python3 -m pytest tests/alerts
python3 -m pytest
```

Documentation-only changes should be manually checked for:

- clear Banking MVP scope
- accurate internal links
- no claims that unbuilt commands already work
- no instructions to circumvent source rules or collect private-session data
- concise agent-readable structure

For Banking MVP readiness hardening, run the focused validation suite and full
offline test suite:

```bash
python3 -m pdi.sources validate --config config/banking_sources.yaml
python3 -m pdi.scoring validate --config config/banking_scoring.yaml
python3 -m pdi.alerts validate --config config/banking_alerts.yaml
python3 -m pytest tests/sources
python3 -m pytest tests/extractors
python3 -m pytest tests/dedupe
python3 -m pytest tests/scoring
python3 -m pytest tests/cli
python3 -m pytest tests/alerts
python3 -m pytest tests/integration
python3 -m pytest
python3 -m pdi --db /tmp/pdi-banking-smoke.sqlite banking smoke-test \
  --digest-output /tmp/pdi-banking-smoke-digest.md \
  --as-of 2026-06-18 \
  --reset-db
```

## AgentOps / RepoOS operating layer

This repository includes a RepoOS-style Continuous AgentOps layer for agent-legible, reviewable work. It adds Codex configuration, hooks, reusable agent skills, lightweight audits, registries, and an AgentOps GitHub Actions workflow without changing Banking MVP product behavior.

Common local checks:

```bash
make agentops-pr
make hooks-smoke
make mcp-smoke
make test
```

`make test` runs the current repo-native test suite with `python3 -m pytest`. Use `make agentops-test` when you want AgentOps checks and pytest together.

AgentOps docs and registries live under `docs/agentops/`. The workflow uses the organization-level self-hosted runner selector documented in `docs/agentops/github-actions-runners.md`.

## Repository docs

- `AGENTS.md` — instructions for implementation agents
- `docs/issue-map.md` — ordered Banking MVP implementation map
- `docs/verification.md` — validation commands and expectations
- `docs/architecture/banking-mvp.md` — system architecture
- `docs/decisions.md` — decision log
- `docs/prompt-library.md` — reusable implementation prompts
- `docs/release-checklists/banking-mvp.md` — first release checklist
- `docs/roadmap/` — post-MVP and deferred feature planning

## Current status

Initial documentation and issue planning are in progress. The Banking MVP now has
a local SQLite storage foundation for raw snapshots, canonical deals, structured
terms, status/change history, explicit source policy validation, local
fixture/manual collector support, and review CLI commands. Offline extraction
and conservative dedupe into canonical deals are implemented, as is transparent
scoring, local alert digest generation, and an offline fixture smoke flow for
canonical deals. Local run history and dry-run run orchestration are
implemented. Credit-card acquisition offers are now MVP scope, with runtime
support tracked in the dedicated Track A/B issues rather than implemented in
this docs-only scope update. Realistic demo source fixtures, product-facing
find/search, fresh-clone demo readiness, built-in live collection, and external
alert sending are not implemented.

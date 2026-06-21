# Banking MVP Architecture

This document describes the initial architecture for the Banking MVP of Personal Deal Intelligence.

## Goal

Build a local-first system that discovers, structures, scores, reviews, and summarizes banking promotions for personal use.

The system should reduce repeated manual deal checking while keeping the user in control of final review and action.

## Scope

Included:

- checking bonuses
- savings bonuses
- checking + savings bundle bonuses
- brokerage transfer/deposit bonuses
- money market and CD bonuses
- publicly available business banking bonuses when clearly separated from personal offers
- personal and business credit card acquisition offers
- local review workflow
- local digest
- offline fixture pipeline

Deferred:

- clothing deals
- travel deals
- flight search
- hotel deals
- cashback stack optimizer
- browser extension
- full hosted app
- automatic financial actions, applications, enrollment, form submission, or money movement
- rewards optimization beyond acquisition offers, including transfer partner assumptions unless explicitly implemented later

## Data flow

```mermaid
flowchart TD
  A[Source Registry] --> B[Collector Framework]
  B --> C[Raw Deal Snapshots]
  C --> D[Banking Extractor]
  D --> E[Deal Candidates]
  E --> F[Dedupe and Canonicalization]
  F --> G[Canonical Banking Deals]
  G --> H[Scoring Engine]
  H --> I[Review CLI]
  H --> J[Alert Digest]
  F --> K[Change Events]
  I --> L[Status Events]
  J --> M[Local Artifacts]
  N[Run History] --> J
  B --> N
```

If Mermaid rendering is not supported in a viewer, treat the diagram as a text representation of the pipeline.

## Layer responsibilities

### 1. Source registry

Purpose: define which banking sources exist and what collection behavior is allowed.

Implemented source policy is config-first. `config/banking_sources.yaml` is the
machine-readable source registry, and `python3 -m pdi.sources validate --config
config/banking_sources.yaml` validates it. The existing SQLite `source_records`
table is provenance for stored snapshots; it is not the policy authority.

Expected source types:

- `manual_url`
- `official_promo_page`
- `rss_feed`
- `newsletter_email`
- `deal_blog`
- `affiliate_feed`
- `api`
- `disabled`

Credit-card source policies should distinguish issuer landing pages, issuer
offer terms pages, issuer business-card pages, public comparison/listing pages
owned by issuers, third-party offer trackers, newsletters/manual exports, and
clearly marked targeted offers from allowed non-private sources.

Each source should define:

- `source_id`
- `source_group`
- `publisher_name`
- `name`
- `url`
- `source_type`
- `source_class`
- `category_scope`
- `subcategory_scope`
- `coverage_purpose`
- `trust_tier`
- `official_source`
- `deposit_account_source`
- `brokerage_source`
- `credit_card_source`
- `fixture_enabled`
- `source_priority`
- `region_scope`
- `enabled`
- `collection_method`
- `max_frequency_hours`
- `requires_login`
- `allow_scrape`
- `allow_api`
- `allow_rss`
- `allow_email_parse`
- `robots_policy_notes`
- `terms_policy_notes`
- `rate_limit_notes`
- `compliance_status`
- `last_reviewed_at`
- `notes`

Allowed source groups are `core`, `demo`, and `public-pilot`. Allowed source
classes are `official`, `third_party`, `manual_import`, and `disabled`; trust
tiers are `official`, `trusted_third_party`, `community`, `user_provided`, and
`disabled`. Source policies must mark whether each source covers deposit
accounts, brokerage bonuses, credit-card offers, or a combination. Official
sources must use the official trust tier, and third-party discovery sources must
not be treated as official evidence.

The `public-pilot` group is disabled by default in checked-in config and is
limited to reviewed public source shapes. For Issue #17, guarded live collection
is RSS-only and requires explicit `--confirm-live`; dry-run planning does not
fetch network content. Public-pilot policy validation rejects missing metadata,
unsafe or unknown fields, login-required live sources, unsupported methods,
unsafe allow flags, and invalid frequency metadata.
The live public-pilot fetch shell is bounded to HTTP/HTTPS public feed or
text-compatible content with URL credential rejection, timeout, max-size,
content-type, and sanitized error metadata checks.

Unsafe behavior is disabled by default. Validation rejects unknown fields,
unsafe source-access flags, logged-in scraping, unapproved enabled sources,
method/allow-flag mismatches, high-frequency scraping, and scopes outside the
Banking MVP.

New source onboarding starts by adding a disabled or fixture-only policy record,
choosing source class/trust tier/category flags, documenting terms and robots
notes, validating with `pdi.sources`, and only then considering a future explicit
enablement path. The current seed pack is intentionally placeholder-only and
does not add new live fetching.

### 2. Collector framework

Purpose: convert allowed sources into raw snapshots.

Implemented collectors are exposed under `pdi.collectors` and normalize raw
content into `CollectedSnapshot` objects that can be persisted to
`raw_deal_snapshots`.

Initial collectors include:

- manual text collector
- manual URL record collector
- RSS/Atom fixture collector
- newsletter/export text collector
- API fixture-backed collector

HTML fetching has no built-in live network client. Any future fetch path must use
an enabled, approved source policy that explicitly allows non-login scraping, and
must pass frequency checks before an injected fetcher can run. Tests use fixtures
or injected fetchers only and must not require internet access by default.

### 3. Raw snapshots

Purpose: preserve source evidence before extraction.

Raw snapshots should include:

- source name
- source URL or identifier
- retrieved timestamp
- content hash
- raw text
- optional raw payload metadata
- HTTP status if relevant
- collector name

Raw snapshots allow re-extraction when extractor logic improves.

### 4. Banking extractor

Purpose: transform raw text into structured banking deal candidates.

Implemented extraction is deterministic and offline-only under `pdi.extractors`.
It reads raw snapshot text and source metadata, produces pre-dedupe
`banking_deal_candidates`, and does not create or update canonical
`banking_deals`.

Extractor identifies:

- institution name
- issuer name for credit-card offers
- promotion title
- card name and visible card network for credit-card offers
- subcategory
- bonus amount
- credit-card offer currency: cash, points, miles, statement credit, or mixed
- headline bonus amount or value
- estimated cash-equivalent value when supported by transparent assumptions
- minimum spend requirement and spend window
- annual fee and first-year fee waiver when present
- statement credits and statement-credit requirements
- business vs personal card classification
- public vs targeted offer classification
- direct deposit requirement
- minimum deposit or balance
- holding period
- monthly fee
- fee waiver terms
- early closure terms
- state restrictions
- new customer restrictions
- expiration date
- evidence spans
- confidence score
- missing fields

Extraction must not guess. Unknown fields should remain null/unknown.
Evidence spans, missing fields, extraction notes, and tiered bonus matches are
stored with candidates for review and later dedupe/canonicalization.
Intro APR and category multipliers are supporting context unless the offer is
explicitly about 0% APR or those multipliers are part of the signup offer terms.
Issuer application restrictions should be captured as review notes, not hard
financial advice.

### 5. Dedupe and canonicalization

Purpose: merge repeated references to the same deal.

Implemented dedupe and canonicalization is exposed under `pdi.dedupe`. It
consumes non-rejected `banking_deal_candidates`, creates or updates canonical
`banking_deals`, links every candidate/source snapshot to
`banking_deal_source_links`, and records material differences in
`deal_change_events`.

Matching uses conservative signals:

- normalized institution name
- issuer and card name for credit-card offers
- subcategory
- bonus amount
- credit-card offer currency, minimum spend, spend window, and annual fee when present
- account/product name
- expiration date if known
- source URL path/domain clues

The layer supports exact canonical-key matches, same-source/product matches, and
strong fuzzy matches by institution, subcategory, bonus amount, compatible
expiration, and compatible product evidence. Low-confidence candidates do not
fuzzy-merge. Important conflicts are preserved in change events and mark the
canonical deal `needs_review` instead of silently overwriting high-confidence or
official-source data.

### 6. Scoring engine

Purpose: rank deals based on expected personal value.

Implemented scoring is exposed under `pdi.scoring` and reads configurable
assumptions from `config/banking_scoring.yaml`. It scores canonical
`banking_deals`, can persist `estimated_net_value_cents` to the existing
canonical row, and returns the full component breakdown for callers.

Scoring components:

- gross bonus value
- estimated cash-equivalent value for credit-card cash, points, miles, statement-credit, or mixed offers
- fee cost
- annual fee cost and first-year waiver when present
- cash lockup opportunity cost
- direct deposit friction
- minimum spend friction and spend-window pressure for credit-card offers
- hassle penalty
- risk/restriction penalty
- targeted/public offer and issuer restriction review adjustment
- missing data penalty
- expiration urgency

Outputs:

- estimated net value
- score from 0 to 100
- score band
- recommended action
- explanation
- missing data warnings

Scoring is transparent and configurable. It is for personal review support only
and must not be presented as financial advice.
Credit-card scoring must not hard-code opaque point or mile valuations without a
configurable assumption and explanation.

### 7. Review CLI

Purpose: let the user inspect and update deals locally.

Implemented commands:

```bash
python3 -m pdi --db data/pdi.sqlite banking list
python3 -m pdi --db data/pdi.sqlite banking show <deal_id>
python3 -m pdi --db data/pdi.sqlite banking update-status <deal_id> <status>
python3 -m pdi --db data/pdi.sqlite banking review-needed
python3 -m pdi --db data/pdi.sqlite banking expiring --days 14
python3 -m pdi --db data/pdi.sqlite banking search --query "checking bonus direct deposit"
python3 -m pdi --db data/pdi.sqlite banking find --query "checking bonus direct deposit"
python3 -m pdi --db data/pdi.sqlite banking search --subcategory checking_bonus --min-bonus 300
python3 -m pdi --db data/pdi.sqlite banking search --recommended-action review_now
python3 -m pdi --db data/pdi.sqlite banking search --expiring-days 14
python3 -m pdi --db data/pdi.sqlite banking search --institution <name>
python3 -m pdi --db data/pdi.sqlite banking score <deal_id>
python3 -m pdi --db data/pdi.sqlite banking demo --reset --seed fixtures
```

The list-style commands support terminal table output by default and JSON with
`--format json`. `list` supports filters for status, institution, subcategory,
score band, recommended action, expiration window, and needs-review state.
`search` and its `find` alias return ranked local results with match reasons,
source labels, score, estimated net value, review indicators, and filters for
query text, institution, subcategory, bonus/net thresholds, score band,
recommended action, status, expiration window, and needs-review state. `demo`
seeds the local synthetic fixture corpus through the offline smoke flow and
writes a local digest artifact for demo review.
`show` includes terms, score explanation, source URLs, missing-data warnings,
source-link references, field-level evidence excerpts for critical terms,
snapshot ids/content hashes, missing-evidence warnings, and status history.
Field-level evidence is derived from stored candidate evidence spans and
canonical source links; it is not a substitute for manual verification on
official institution or issuer pages.

Status updates create `deal_status_events` records and update the local
canonical deal status. Status values include `new`, `needs_review`, `watching`,
`interested`, `in_progress`, `completed`, `skipped`, `expired`, and `rejected`;
legacy `applied` rows remain accepted for compatibility.

The CLI is a personal review aid only. It does not request credentials, perform
applications, submit forms, enroll in offers, or move money. It must not store
full card numbers or sensitive personal financial information. Final offer
terms should be verified on the official institution or issuer page before
acting.

### 8. Digest

Purpose: summarize high-signal deals.

Implemented alert digest support is exposed under `pdi.alerts` and through
`python3 -m pdi banking digest`. It reads canonical deals, scoring outputs,
source links, change events, and status events from the local SQLite database,
then writes local markdown or JSON artifacts.

Digest sections:

- Review Now
- Expiring Soon
- Changed Deals
- Needs More Information
- Watchlist Updates

Digest outputs are local markdown first, with JSON available for deterministic
tests and future automation.
Credit-card digest entries should show acquisition-offer fields when available,
including issuer, card name, offer currency, headline value, estimated
cash-equivalent value, minimum spend, spend window, annual fee, public/targeted
classification, missing critical fields, and source evidence.

External notifications are disabled by default. The implemented notification
hook is no-op/dry-run only and does not send live messages.

### 8a. Offline fixture smoke flow

Purpose: prove the Banking MVP components work together without live sources.

Implemented smoke support is exposed under `pdi.smoke` and through
`python3 -m pdi banking smoke-test`. It loads synthetic local text fixtures,
creates raw snapshots, extracts candidates, canonicalizes duplicates and
conflicts, scores canonical deals, writes a local markdown digest, and prints
summary counts.

The smoke flow is fixture-only. It does not fetch websites, use browser
automation, connect email accounts, send external messages, or automate banking
actions.

### 8b. Reusable demo corpus

Purpose: provide realistic local demo source inputs without live collection.

Issue #14 adds `config/banking_sources.demo.yaml` and `examples/demo_banking/`
as a synthetic source seed pack. The corpus covers official-page style fixtures,
deal-blog RSS content, newsletter export text, manual pasted notes, disabled
source policy coverage, duplicates, conflicts, expired and low-value offers,
ambiguous terms, non-deal content, and the main Banking MVP subcategories.

The demo corpus is loaded through existing offline collectors and source policy
validation, and the fresh-clone demo gate uses it through local CLI commands. It
does not add live fetching, browser automation, email account access,
credentials, notifications, or banking actions.

The local QA benchmark is exposed through `python3 -m pdi banking qa-benchmark`.
It reuses the demo corpus to check expected deal coverage, duplicate merging,
conflict surfacing, non-deal suppression, score sanity, and edge-case fixture
coverage. It is deterministic and offline-only. Credit-card runtime coverage is
reported as pending until the credit-card extraction/scoring path exists.

### 8c. Opt-in public-pilot sources

Purpose: prove the public-source collection shape without enabling broad live
collection or managed source coverage.

Issue #17 adds a `public-pilot` source group and one disabled RSS placeholder in
`config/banking_sources.yaml`. `python3 -m pdi banking sources list` shows
source id, group, method, enabled status, review metadata, and safety state.
`python3 -m pdi banking sources validate` validates policy metadata. `python3
-m pdi banking run --dry-run --sources public-pilot` plans collection without
network access. `python3 -m pdi banking run --sources public-pilot
--confirm-live` is the only live path and proceeds only when an enabled,
approved, policy-valid RSS source is present in local config.

The default public-pilot config has no enabled live sources. If none are
enabled, the run exits successfully with `No enabled public pilot sources
configured.` Public-pilot collection does not support credentials, private
sessions, browser automation, external notifications, applications, enrollment,
money movement, or non-MVP product categories. Final offer terms still require
manual verification on the official institution page.

### 9. Run history

Purpose: track repeated runs and failures.

Implemented run history support is exposed through `pdi.runs` and through:

```bash
python3 -m pdi --db data/pdi.sqlite banking run
python3 -m pdi --db data/pdi.sqlite banking run --dry-run
python3 -m pdi --db data/pdi.sqlite banking run --execute
python3 -m pdi --db data/pdi.sqlite banking runs --limit 10
python3 -m pdi --db data/pdi.sqlite banking run-status <run_id>
```

Run records include:

- run id
- start time
- end time
- status
- dry-run flag
- source counts
- candidate counts
- canonical deal counts
- conflicts
- errors
- digest path

The default run mode is dry-run. Dry-run records only run history in the real
database, executes the workflow against a temporary database copy, avoids
durable digest writes, and stores the requested digest path as metadata. Durable
workflow changes require explicit `--execute`.

Overlapping runs are blocked by a SQLite lock row with a unique `lock_name` and
local owner metadata. The lock is released after successful or failed runs.
Blocked runs are recorded without taking over the existing lock. Stale lock
cleanup is intentionally manual for now.

## Storage model

The first storage implementation uses SQLite with stdlib `sqlite3`, versioned
SQL migrations, and package helpers under `src/pdi/storage/`.

Implemented SQLite-backed concepts:

- source records
- raw deal snapshots
- canonical banking deals
- banking deal terms
- extracted banking deal candidates
- canonical deal source links
- deal status events
- deal change events
- banking run history
- banking run locks

Future issues may add score records if durable score history becomes useful.

## Configuration

Expected config files:

- `config/banking_sources.yaml` (implemented)
- `config/banking_scoring.yaml` (implemented)
- `config/banking_alerts.yaml` (implemented)

Do not store secrets in config files. Use environment variables only if external integrations are later added.

## Safety boundaries

The architecture must keep:

- source collection limited to configured allowed methods
- private-session data outside automated collection
- private auth material and highly sensitive personal identifiers outside project storage
- full card numbers and sensitive personal financial information outside project storage
- financial actions, card applications, form submission, enrollment, and money movement under direct user control
- personalized financial advice outside system behavior
- anti-bot protections, paywalls, CAPTCHAs, and access controls respected without bypass
- external notifications and live collection disabled unless a future issue adds explicit policy, tests, and review steps

## First usable MVP

The first usable release should support:

1. offline fixture pipeline
2. local database
3. structured extraction from sample banking and credit-card acquisition promotion text
4. dedupe/canonicalization
5. score calculation
6. CLI review
7. local digest generation

Live sources can be added only after source policy, fixture tests, and safety checks are stable.

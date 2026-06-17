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
- local review workflow
- local digest
- offline fixture pipeline
- run history

Deferred:

- clothing deals
- travel deals
- flight search
- hotel deals
- cashback stack optimizer
- browser extension
- full hosted app

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

Expected source types:

- `manual_url`
- `official_promo_page`
- `rss_feed`
- `newsletter_email`
- `deal_blog`
- `affiliate_feed`
- `api`
- `disabled`

Each source should define:

- name
- URL or source identifier
- category/subcategory scope
- enabled flag
- allowed collection methods
- frequency limit
- compliance notes
- last reviewed date

Unsafe behavior should be disabled by default.

### 2. Collector framework

Purpose: convert allowed sources into raw snapshots.

Initial collectors should prioritize:

- manual text collector
- fixture collector
- RSS fixture collector
- newsletter/export text collector
- API placeholder or fixture-backed collector

Network collection should be policy-controlled and tested separately. Tests must use fixtures by default.

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

Extractor should identify:

- institution name
- promotion title
- subcategory
- bonus amount
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

### 5. Dedupe and canonicalization

Purpose: merge repeated references to the same deal.

Matching should use conservative signals:

- normalized institution name
- subcategory
- bonus amount
- account/product name
- expiration date if known
- source URL path/domain clues

The system should preserve all source references and record conflicts instead of silently overwriting important fields.

### 6. Scoring engine

Purpose: rank deals based on expected personal value.

Scoring components:

- gross bonus value
- fee cost
- cash lockup opportunity cost
- direct deposit friction
- hassle penalty
- risk/restriction penalty
- missing data penalty
- expiration urgency

Outputs:

- estimated net value
- score from 0 to 100
- score band
- recommended action
- explanation
- missing data warnings

Scoring must be transparent and configurable.

### 7. Review CLI

Purpose: let the user inspect and update deals locally.

Expected commands:

```bash
pdi banking list
pdi banking show <deal_id>
pdi banking update-status <deal_id> <status>
pdi banking review-needed
pdi banking expiring --days 14
pdi banking search --institution <name>
pdi banking score <deal_id>
```

These are target commands and should be updated once implementation exists.

### 8. Digest

Purpose: summarize high-signal deals.

Digest sections:

- Review Now
- Expiring Soon
- Changed Deals
- Needs More Information
- Watchlist Updates

Digest outputs should be local markdown first, with optional JSON.

External notifications should be disabled by default.

### 9. Run history

Purpose: track repeated runs and failures.

Run records should include:

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

## Storage model

Expected SQLite-backed concepts:

- source records
- raw deal snapshots
- banking deal candidates
- canonical banking deals
- banking deal terms
- deal source links
- deal status events
- deal change events
- score records
- run history

The exact schema should be finalized in issue #2.

## Configuration

Expected config files:

- `config/banking_sources.yaml`
- `config/banking_scoring.yaml`
- `config/banking_alerts.yaml`

Do not store secrets in config files. Use environment variables only if external integrations are later added.

## Safety boundaries

The architecture must keep:

- source collection limited to configured allowed methods
- private-session data outside automated collection
- private auth material and highly sensitive personal identifiers outside project storage
- financial actions, applications, enrollment, and money movement under direct user control
- external notifications and live collection disabled unless a future issue adds explicit policy, tests, and review steps

## First usable MVP

The first usable release should support:

1. offline fixture pipeline
2. local database
3. structured extraction from sample banking promotion text
4. dedupe/canonicalization
5. score calculation
6. CLI review
7. local digest generation

Live sources can be added only after source policy, fixture tests, and safety checks are stable.

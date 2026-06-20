# PersonalDealIntelligence GitHub Issue Batch

Repository: `amanm02/PersonalDealIntelligence`

Total issues: 17


---

## 1. Banking MVP 17: Expand MVP scope to include credit card offers

## Objective
Update the Banking MVP operating docs, roadmap, issue map, architecture, and release definition so credit card acquisition offers are included in the MVP instead of being deferred.

This is a documentation and scope-alignment issue only. It should make the repo's source-of-truth docs accurately reflect that the MVP covers both deposit/brokerage banking promotions and credit card acquisition offers.

## Product context
The MVP goal is to find and track new customer financial promotions across all major account types. The current Banking MVP docs emphasize checking, savings, checking+savings bundles, brokerage, money market, and CD offers, while credit cards are not fully represented. That creates a roadmap gap: future agents may build the data model, extraction, scoring, and source policies around deposit bonuses only.

Credit cards must be included in the MVP with their own source, schema, extraction, scoring, and review requirements because their offer structure differs from deposit accounts.

## Dependencies
- Depends on existing operating docs from issue #1.
- Should be completed before implementing the new Track A/B source coverage, taxonomy, schema, extraction, scoring, and review issues in this batch.

## Instructions
Read in order:
1. `AGENTS.md`
2. `README.md`
3. `docs/issue-map.md`
4. `docs/architecture/banking-mvp.md`
5. `docs/verification.md`
6. `docs/decisions.md`
7. `docs/prompt-library.md` if present
8. GitHub issues #1 through current open issues
9. This issue body
10. Only the files needed for this documentation update

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required scope updates
Update docs to make the MVP explicitly include:

### Banking deposit/brokerage account offers
- checking account bonuses
- savings account bonuses
- checking + savings bundle bonuses
- money market bonuses
- CD bonuses
- brokerage transfer/deposit bonuses
- business banking bonuses when publicly available and clearly separated from personal offers

### Credit card acquisition offers
- personal credit card signup bonuses
- business credit card signup bonuses
- cash bonus offers
- points offers
- miles offers
- statement-credit offers
- elevated limited-time offers
- publicly available issuer offers
- clearly marked targeted offers if discovered from allowed, non-private sources

## Required credit card concepts to document
Add credit-card-specific MVP concepts to architecture and roadmap docs:
- issuer
- card name
- card network if visible
- offer currency: cash, points, miles, statement credit, mixed
- headline bonus amount/value
- estimated cash-equivalent value
- minimum spend requirement
- spend window
- annual fee
- first-year fee waiver if present
- statement credits
- intro APR only as supporting context, not as primary deal value unless the offer is explicitly about 0% APR
- category multipliers only as supporting context unless part of signup offer terms
- transfer partner assumptions deferred unless explicitly implemented later
- issuer application restrictions as review notes, not hard financial advice
- business vs personal card classification
- public vs targeted offer classification

## Required docs updates
Update all relevant docs so they agree:
- `README.md`
- `docs/issue-map.md`
- `docs/architecture/banking-mvp.md`
- `docs/verification.md`
- `docs/decisions.md`
- `docs/release-checklists/banking-mvp.md` if present
- any prompt-library or roadmap file that still says credit cards are deferred

## Required issue-map behavior
The issue map should:
- mark credit card support as in-scope for MVP
- preserve the existing local-first, safe, policy-driven implementation style
- show that credit-card support is implemented through dedicated Track A/B issues, not crammed into existing deposit-only components
- make dependencies clear enough for Codex to implement one issue at a time

## Safety and compliance boundaries
Document that the system must not:
- apply for cards
- recommend financial actions as personalized financial advice
- submit forms
- store full card numbers or sensitive personal financial information
- scrape private sessions or authenticated pages unless a future issue explicitly adds a safe manual import flow
- bypass anti-bot protections, paywalls, CAPTCHAs, or access controls

The system may:
- collect public offer pages when source policy allows it
- ingest manually provided/publicly available offer text
- preserve evidence
- rank offers based on transparent assumptions
- flag offers for user review

## Acceptance criteria
- Credit cards are no longer listed as deferred if any doc currently implies that.
- Architecture docs include credit-card-specific source, data, extraction, scoring, and review concepts.
- Issue map reflects the new Track A/B implementation sequence.
- Release checklist includes credit card fixtures and validation.
- Safety boundaries explicitly cover credit-card application and private-session limits.
- No runtime implementation is added unless required to keep docs/tests passing.

## Validation
Run the relevant documentation validation from `docs/verification.md`. At minimum, run any markdown/doc checks available in the repo. If no doc validation command exists, document that clearly in the PR.



---

## 2. Banking MVP 18: Build comprehensive banking and credit card source universe with onboarding workflow

## Objective
Create a comprehensive, policy-controlled source universe and source onboarding workflow for the MVP's banking and credit card promotion research engine.

This issue expands the existing source registry concept from placeholder/sample sources into an organized source coverage layer that Codex and the user can maintain over time.

## Track
Track A: Research + Collection Engine

## Product context
The always-on value of Personal Deal Intelligence depends on source coverage. A clean demo pipeline is not enough if the system does not know where to look. The source universe should enumerate the public or permissioned places where deposit, brokerage, and credit card promotions are likely to appear, while keeping collection methods conservative and compliant.

## Dependencies
- Depends on source registry/source policy work from issue #3.
- Depends on credit card MVP scope update from Banking MVP 17.
- Should precede broad live-source expansion and research QA benchmarking.

## Instructions
Read in order:
1. `AGENTS.md`
2. `README.md`
3. `docs/issue-map.md`
4. `docs/architecture/banking-mvp.md`
5. `docs/decisions.md`
6. existing source registry/config files
7. existing collector code and tests
8. this issue body
9. only the files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required source categories
Add or document source categories for:

### Official deposit/banking sources
- bank checking promotion pages
- bank savings promotion pages
- bank CD and money market promotion/rate pages
- bank business checking/savings promo pages
- regional/community bank promotion pages
- brokerage transfer/deposit bonus pages
- institution disclosures or offer terms pages

### Official credit card sources
- issuer credit card landing pages
- issuer elevated-offer pages
- issuer business-card pages
- issuer card offer terms pages
- card comparison/listing pages owned by issuers
- public prequalification or marketing pages only if collection does not require private data or form submission

### Third-party sources
- deal blogs
- banking bonus aggregator pages
- credit card offer tracking pages
- RSS feeds
- newsletters/manual exports
- affiliate feed placeholders
- API placeholders where a legitimate API/feed exists or may exist later

## Required source fields
Extend or validate the source registry so each source can store:
- stable source id
- source name
- institution or publisher name
- source type
- product category scope
- product subcategory scope
- URL or source identifier
- source owner/contact if known
- coverage purpose
- collection method
- allowed collection modes
- network enabled flag
- fixture enabled flag
- max frequency hours
- region/state scope if relevant
- public vs permissioned vs manual-import source class
- compliance status
- compliance notes
- last policy review date
- last successful collection timestamp
- source priority
- source trust tier
- official-source flag
- credit-card source flag
- deposit-account source flag
- notes

## Required onboarding workflow
Implement the smallest practical onboarding flow. It may be CLI-first or config-first depending on current repo structure.

The workflow should support:
- adding a source in disabled or fixture-only mode by default
- validating required fields
- marking a source as official, third-party, manual, or disabled
- reviewing source policy notes before enabling live collection
- listing sources by category, source type, trust tier, and enabled state
- identifying missing policy fields
- documenting how a new source should be reviewed before collection

## Required seed pack
Create or update a seed pack with realistic placeholder sources. Use safe example domains or clearly disabled real sources if the project already has a policy pattern for that.

Seed examples should cover:
- national bank checking promotion page
- national bank savings offer page
- brokerage bonus page
- money market/CD promo page
- credit card issuer card detail page
- credit card issuer terms page
- third-party banking bonus blog source
- third-party credit card offers source
- RSS/newsletter/manual source

## Non-goals
- Do not fetch live pages in this issue.
- Do not implement scraping/browser automation.
- Do not add private-session or authenticated collection.
- Do not bypass site restrictions.
- Do not implement scoring, extraction, or UI changes except as needed to support source metadata.

## Acceptance criteria
- Source registry supports deposit, brokerage, and credit card promotion sources.
- Source validation catches missing critical policy fields.
- New sources default to safe disabled or fixture-only behavior unless explicitly enabled by policy.
- CLI or documented workflow exists for reviewing/onboarding sources.
- Tests cover valid and invalid source configs.
- Docs explain source trust tiers and source onboarding steps.

## Validation
Run source policy validation, unit tests for source registry/config parsing, and any existing docs/test validation.



---

## 3. Banking MVP 19: Add compliant live fetcher hardening, retry rules, rate limits, and source health tracking

## Objective
Harden the live collection layer so approved public sources can be fetched safely, predictably, and conservatively without weakening compliance or reliability boundaries.

## Track
Track A: Research + Collection Engine

## Product context
The current collector framework is intentionally local-first and fixture-driven. To become useful for real public sources, the system needs safe live-fetch behavior: rate limits, retries, timeouts, source health, failure handling, and deterministic tests that do not require internet access.

This issue should prepare the foundation for approved live source collection while keeping live fetching opt-in and controlled by source policy.

## Dependencies
- Depends on issue #3 source policy.
- Depends on issue #4 collector framework.
- Depends on Banking MVP 18 source universe/onboarding.
- Should be completed before broad source coverage expansion.

## Instructions
Read in order:
1. `AGENTS.md`
2. `docs/architecture/banking-mvp.md`
3. `docs/issue-map.md`
4. `docs/verification.md`
5. source registry/config files
6. collector framework files
7. storage/schema files if source health is persisted
8. this issue body
9. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required fetcher behavior
Implement or extend a compliant HTTP fetcher abstraction that supports:
- source-policy check before network access
- disabled-by-default network fetching in tests
- configurable user agent if the repo already has config conventions
- request timeout
- max response size
- redirect handling with policy-aware final URL recording
- content-type detection
- text/html, text/plain, application/rss+xml, application/atom+xml, JSON where appropriate
- response status recording
- response headers metadata where safe
- content hash generation
- deterministic fixture mode

## Required retry/rate behavior
Add conservative behavior:
- per-source minimum interval based on `max_frequency_hours`
- no overlapping fetches for the same source
- retry only on transient failures
- capped retry count
- exponential or fixed backoff configured locally
- do not retry on forbidden, not found, policy-blocked, or unsupported content errors
- record skip reason when a fetch is blocked by policy/frequency

## Required source health tracking
Track source health either in SQLite or a structured local artifact, depending on existing storage patterns.

Fields should include:
- source id
- last attempted at
- last successful at
- last failure at
- last status code
- consecutive failure count
- last error type
- last error message sanitized
- last content hash
- last changed at
- last unchanged at
- last snapshot id if available
- policy blocked count
- frequency skipped count

## Required CLI/reporting behavior
Add or update commands equivalent to:
- `pdi banking sources list`
- `pdi banking sources health`
- `pdi banking sources show <source_id>`
- `pdi banking sources validate`
- `pdi banking collect --source <source_id> --dry-run`
- `pdi banking collect --source <source_id> --allow-network` only if source policy allows it

Use the project's existing CLI conventions if different.

## Testing requirements
Tests must:
- not call the internet by default
- mock HTTP responses or use local fixtures
- verify policy-blocked fetches do not call network code
- verify timeout/retry behavior using mocks
- verify frequency limits skip collection
- verify source health updates on success/failure/skip
- verify content hashes are stable

## Safety boundaries
Do not add:
- browser automation
- proxies
- CAPTCHA handling
- anti-bot bypass
- authenticated/private collection
- form submission
- card application actions
- banking login handling

## Acceptance criteria
- Approved live fetch behavior exists but remains opt-in.
- Policy checks block unapproved network collection.
- Source health is visible and testable.
- Retries and rate limits are deterministic in tests.
- Docs explain how to run a safe dry run and how to enable a source only after review.



---

## 4. Banking MVP 20: Add evidence capture with raw snapshots, content hashes, and source-term links

## Objective
Strengthen evidence capture so every extracted banking or credit card offer term can be traced back to raw source material.

## Track
Track A + Track B integration

## Product context
This system should not overclaim financial offer terms. Banking and credit card promotions change frequently, and terms may conflict across sources. The MVP needs durable evidence: raw snapshots, content hashes, retrieval metadata, and source-term links that allow re-extraction and reviewer verification.

## Dependencies
- Depends on issue #2 storage/schema.
- Depends on issue #4 collector framework.
- Depends on issue #5 extraction.
- Depends on Banking MVP 19 fetcher hardening if live metadata is reused.
- Should precede stronger conflict resolution and QA benchmark work.

## Instructions
Read in order:
1. `AGENTS.md`
2. `docs/architecture/banking-mvp.md`
3. `docs/verification.md`
4. storage migrations/schema files
5. raw snapshot models
6. extractor candidate models
7. collector/fetcher code
8. this issue body
9. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required evidence model
Implement or extend storage/models for:
- raw source snapshot
- normalized extracted text
- content hash
- snapshot hash
- source id
- source URL or identifier
- final URL if redirects are followed
- retrieved timestamp
- collector name/version if available
- parser/extractor version if available
- source title/page title when available
- HTTP status if relevant
- content type if relevant
- raw text
- optional raw HTML path or blob reference if the repo has a safe artifact pattern
- optional screenshot/PDF evidence path only if already supported safely or deferred explicitly
- metadata JSON for non-sensitive retrieval context

## Required source-term links
Each extracted candidate term should support evidence links for:
- field name
- extracted value
- source snapshot id
- evidence text span or excerpt
- character start/end if practical
- confidence
- extraction method
- created timestamp

Apply this to both deposit/brokerage and credit-card fields.

Examples:
- checking bonus amount -> source span
- direct deposit requirement -> source span
- APY -> source span
- CD term length -> source span
- credit card minimum spend -> source span
- credit card annual fee -> source span
- credit card spend window -> source span
- expiration date -> source span

## Required re-extraction support
Preserve enough evidence so future extractor versions can:
- reprocess stored snapshots
- compare old vs new extraction outputs
- identify changed extracted terms
- retain prior extraction evidence
- avoid overwriting manually reviewed values without an audit trail

## Required CLI/review behavior
Update relevant CLI/review commands so a user can inspect evidence for a deal:
- show source list for a deal
- show source snapshot metadata
- show field-level evidence for critical terms
- flag fields with missing evidence
- flag fields extracted from third-party sources only

Exact commands may follow current CLI style.

## Required tests
Tests should cover:
- snapshot content hashing
- duplicate snapshot hash behavior
- evidence link creation for extracted fields
- missing evidence warnings
- re-extraction from stored snapshot fixtures
- credit-card field evidence links
- deposit/brokerage field evidence links

## Non-goals
- Do not implement large binary artifact storage unless already supported.
- Do not store private-session data.
- Do not store sensitive personal financial information.
- Do not add screenshot capture unless it can be done safely and is clearly documented.

## Acceptance criteria
- Extracted critical terms can be traced to raw snapshot evidence.
- Snapshots are hashable and dedupable.
- CLI/review output exposes evidence in a useful way.
- Tests prove field-level evidence exists for both banking and credit-card fixtures.
- Docs explain evidence preservation and re-extraction behavior.



---

## 5. Banking MVP 21: Add freshness scheduling, stale-source detection, and recrawl priority rules

## Objective
Add local-first freshness and recrawl planning so the system can decide what to check next without relying on ad hoc manual runs.

## Track
Track A: Research + Collection Engine

## Product context
An always-on deal intelligence system needs to manage freshness. Some sources change daily, others rarely change, and expiring offers need more frequent verification. The MVP should have a deterministic local scheduler/planner that recommends or runs source checks based on policy, source health, product category, and offer urgency.

## Dependencies
- Depends on issue #3 source policy.
- Depends on issue #12 run history.
- Depends on Banking MVP 18 source universe/onboarding.
- Depends on Banking MVP 19 source health tracking.
- Useful before public source expansion and QA benchmarking.

## Instructions
Read in order:
1. `AGENTS.md`
2. source registry/config
3. run history implementation
4. source health implementation
5. canonical deal/change event storage
6. docs/architecture and verification docs
7. this issue body
8. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required planner behavior
Create a recrawl/freshness planner that can:
- identify sources due for collection based on `max_frequency_hours`
- skip disabled sources
- skip policy-blocked sources
- prioritize official sources over third-party sources when verifying known deals
- prioritize sources related to expiring deals
- deprioritize sources with repeated failures
- identify stale sources with no successful collection in a configured window
- identify stale deals with no recent supporting evidence
- produce a dry-run plan without fetching anything

## Required configuration
Add or extend configuration for:
- default recrawl interval by source type
- maximum source age before stale warning
- maximum deal evidence age before stale warning
- expiring-soon window
- failure backoff thresholds
- source priority weights
- official verification priority
- credit-card offer freshness window
- deposit/brokerage offer freshness window
- rate/APY freshness window

## Required commands
Add or update CLI commands equivalent to:
- `pdi banking plan-refresh`
- `pdi banking plan-refresh --category credit_card`
- `pdi banking plan-refresh --official-only`
- `pdi banking stale-sources`
- `pdi banking stale-deals`
- `pdi banking run --planned --dry-run`

Use existing CLI conventions if different.

## Required output
The planner output should include:
- source id
- source name
- reason due
- priority score or rank
- last success
- last failure
- related deal ids if relevant
- expected collection method
- whether network is allowed by policy
- skip reason if not eligible
- stale warnings

## Required tests
Tests should cover:
- due source selection
- disabled source exclusion
- policy-blocked source exclusion
- failure backoff
- expiring deal priority
- stale deal detection
- credit-card source freshness
- APY/rate source freshness
- deterministic dry-run output

## Acceptance criteria
- The system can produce a deterministic refresh plan.
- Stale sources and stale deals are visible.
- Planner does not fetch the internet during tests.
- Docs explain how to review and run the refresh plan.
- Run history records planned/dry-run executions when integrated.



---

## 6. Banking MVP 22: Add official-source verification workflow for third-party deal discoveries

## Objective
Add a verification workflow that distinguishes third-party discoveries from offers confirmed by official bank, brokerage, or issuer sources.

## Track
Track A + Track B integration

## Product context
Deal blogs, newsletters, and aggregators are useful for discovery, but the system should not treat third-party claims as fully verified financial offer terms. The MVP needs a workflow that can promote a discovered offer into a verified offer only when official evidence supports the key terms.

## Dependencies
- Depends on source trust tiers from Banking MVP 18.
- Depends on evidence capture from Banking MVP 20.
- Depends on canonicalization/change tracking from issue #6.
- Should precede conflict resolution and user-facing ranking refinements.

## Instructions
Read in order:
1. `AGENTS.md`
2. source registry/config
3. evidence snapshot/linking code
4. canonical deal and candidate models
5. review CLI code
6. scoring/digest code
7. this issue body
8. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required verification statuses
Add or support verification statuses:
- `unverified`
- `third_party_only`
- `official_source_found`
- `official_terms_confirmed`
- `official_terms_conflict`
- `expired_on_official_source`
- `needs_manual_review`
- `rejected`

These statuses should be applicable to deposit/brokerage deals and credit card offers.

## Required official matching behavior
Implement conservative matching between third-party discoveries and official sources using:
- institution/issuer name
- product/card/account name
- offer amount or bonus currency
- category/subcategory
- expiration date if present
- URL/domain/source hints
- terms page references

Do not auto-verify if key details conflict.

## Critical terms to verify
For deposit/brokerage:
- bonus amount
- account type/product name
- minimum deposit/balance
- direct deposit requirement
- holding period
- monthly fee or fee waiver
- expiration date
- state restrictions
- new customer restrictions

For credit cards:
- issuer
- card name
- bonus amount/currency
- minimum spend requirement
- spend window
- annual fee
- expiration or limited-time language
- personal/business classification
- targeted/public classification
- key eligibility or issuer restrictions if visible

## Required review behavior
The user should be able to:
- list unverified deals
- list third-party-only deals
- list deals with official conflicts
- inspect evidence side by side
- mark a deal as verified, rejected, or needs review
- preserve reviewer notes
- avoid overwriting official fields with lower-trust third-party fields

## Required scoring/digest behavior
Update scoring/digest logic so:
- unverified deals receive quality warnings
- third-party-only deals can still appear but are marked clearly
- official conflicts are routed to review
- official-source verified deals are preferred where appropriate
- missing official confirmation is not hidden

## Required tests
Tests should cover:
- third-party discovery without official verification
- successful official match
- official conflict
- credit card third-party discovery and official verification
- reviewer status updates
- scoring/digest warnings for unverified deals

## Acceptance criteria
- Official verification state exists and is visible.
- Third-party discoveries do not become fully verified without official evidence.
- Conflicts between third-party and official terms are preserved for review.
- CLI/digest outputs clearly mark verification status.
- Tests cover both banking and credit-card examples.



---

## 7. Banking MVP 23: Expand public source pilot into managed source coverage library

## Objective
Turn the small opt-in public source pilot into a managed source coverage library for MVP banking, brokerage, and credit card offers.

## Track
Track A: Research + Collection Engine

## Product context
The public source pilot proves one or a few approved sources can be collected safely. The MVP needs a broader managed coverage library so the system can discover current offers across product categories while retaining policy review and source health controls.

## Dependencies
- Depends on issue #17 public source pilot.
- Depends on Banking MVP 18 source universe/onboarding.
- Depends on Banking MVP 19 fetcher hardening.
- Depends on Banking MVP 21 freshness planner.
- Depends on Banking MVP 22 official verification workflow.

## Instructions
Read in order:
1. `AGENTS.md`
2. source registry/config files
3. collector/fetcher implementation
4. source health/freshness planner
5. verification workflow
6. docs and verification commands
7. this issue body
8. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required coverage library behavior
Create or update a managed source coverage library that can be grown safely over time.

It should organize sources by:
- product category
- institution/issuer/publisher
- source type
- official vs third-party
- enabled state
- collection method
- policy status
- trust tier
- freshness tier
- coverage notes

## Required initial coverage targets
Include enough sources or disabled seed entries to represent:
- checking bonuses
- savings bonuses
- money market/CD offers
- brokerage bonuses
- business banking bonuses
- personal credit card signup offers
- business credit card signup offers
- third-party banking bonus sources
- third-party credit card offer sources
- RSS/newsletter/manual import sources

Use safe defaults. Sources may be disabled by default until reviewed.

## Required source review workflow
Add or document a process for moving a source through:
1. proposed
2. policy reviewed
3. fixture tested
4. live pilot enabled
5. monitored
6. disabled or deprecated

## Required reporting
Add or update reporting so the user can see:
- coverage by product category
- official source coverage gaps
- third-party-only categories
- sources disabled for policy reasons
- sources failing collection
- sources stale or never collected
- categories with no active sources

## Required tests
Tests should verify:
- coverage library loads
- categories are complete enough for MVP
- disabled sources do not collect
- missing official coverage is reported
- credit-card sources are included
- source coverage report is deterministic

## Non-goals
- Do not scrape high-risk or blocked websites.
- Do not bypass anti-bot protections.
- Do not require internet for tests.
- Do not implement a web dashboard.

## Acceptance criteria
- Managed source coverage library exists and includes credit-card sources.
- Coverage reporting identifies gaps by category.
- Source review lifecycle is documented.
- Tests validate coverage library structure and safe defaults.



---

## 8. Banking MVP 24: Add research QA benchmark for missed, stale, duplicate, and incorrectly extracted deals

## Objective
Create a research QA benchmark that measures whether the system is actually finding, extracting, deduping, and scoring known banking and credit card offers correctly.

## Track
Track A + Track B validation

## Product context
A deal intelligence system can have passing unit tests but still fail at its main job: finding current offers accurately. The MVP needs benchmark fixtures and repeatable QA commands that simulate known deals, stale deals, duplicate deals, conflicts, and credit-card offers.

## Dependencies
- Depends on extraction from issue #5.
- Depends on dedupe/change tracking from issue #6.
- Depends on scoring from issue #7.
- Depends on offline smoke test from issue #10.
- Depends on realistic fixture corpus from issue #14.
- Depends on credit card model/scoring issue if not already implemented; otherwise use expected pending/skipped markers.

## Instructions
Read in order:
1. `AGENTS.md`
2. `docs/verification.md`
3. fixture corpus
4. extractor tests
5. dedupe tests
6. scoring tests
7. review/digest tests
8. this issue body
9. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required benchmark scenarios
Create deterministic local fixtures for:

### Deposit/brokerage offers
- active checking bonus
- active savings bonus
- checking+savings bundle
- brokerage transfer bonus
- CD/money market APY/rate offer
- expired deposit offer
- duplicate deposit offer across two sources
- conflicting deposit terms across official and third-party source

### Credit card offers
- cash signup bonus
- points signup bonus
- miles signup bonus
- statement credit offer
- personal card offer
- business card offer
- offer with annual fee
- offer with first-year annual fee waived
- duplicate credit card offer across official and third-party source
- conflicting credit card spend requirement
- targeted offer that should require review

### Negative/control fixtures
- non-deal marketing page
- generic APY/rate page with no promo
- credit card benefits page with no signup offer
- old article referencing an expired offer

## Required benchmark metrics
The QA command should report:
- total fixtures processed
- sources processed
- snapshots created
- candidates extracted
- canonical deals created
- duplicates merged
- conflicts detected
- expected deals found
- expected deals missed
- false positives
- stale/expired correctly classified
- critical field accuracy count
- score sanity pass/fail
- verification status pass/fail

## Required commands
Add a command equivalent to:
- `pdi banking qa-benchmark`
- `pdi banking qa-benchmark --json`
- `pdi banking qa-benchmark --category credit_card`
- `pdi banking qa-benchmark --category deposit`

Use existing CLI conventions if different.

## Required acceptance thresholds
Define minimum local benchmark thresholds. At minimum:
- all fixture-backed expected deals are found
- all known duplicates are merged
- all known conflicts are flagged
- non-deal fixtures do not create canonical deals
- critical credit-card fields are extracted from credit-card fixtures
- stale/expired fixture offers are classified correctly

## Required tests
Add tests for:
- benchmark command runs offline
- JSON output is deterministic
- expected misses fail the benchmark
- duplicate failures fail the benchmark
- credit-card fixture coverage exists
- benchmark does not require live internet

## Acceptance criteria
- Research QA benchmark exists and runs offline.
- Benchmark includes deposit/brokerage and credit-card fixtures.
- Benchmark reports missed/stale/duplicate/incorrect extraction metrics.
- Validation docs explain how to run and interpret the benchmark.



---

## 9. Banking MVP 25: Add explicit candidate, source-link, score, and run-history persistence tables

## Objective
Extend the SQLite data model so the MVP can persist intermediate candidates, explicit deal-source links, score records, and run history instead of keeping them implied or transient.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
The architecture notes that future issues may add deal candidates, explicit deal source links, score records, and run history. These should be first-class persisted concepts for a serious deal intelligence database. Without them, the system cannot audit extraction decisions, rerun scoring, explain source coverage, or support a future UI/API cleanly.

## Dependencies
- Depends on issue #2 storage/schema.
- Depends on issue #5 extraction.
- Depends on issue #6 canonicalization/change tracking.
- Depends on issue #7 scoring.
- Depends on issue #12 run history if already implemented.
- Should precede query/service layer and audit/export issues.

## Instructions
Read in order:
1. `AGENTS.md`
2. storage migration conventions
3. existing SQLite schema
4. extractor/candidate models
5. canonical deal models
6. scoring models
7. run history implementation
8. docs/architecture and verification docs
9. this issue body
10. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required persisted concepts
Add migrations/models/helpers for:

### Deal candidates
- candidate id
- source snapshot id
- source id
- product category
- product subcategory
- institution/issuer
- product/card/account name
- title
- extracted fields JSON or normalized related tables
- confidence
- missing critical fields
- extraction version
- created at

### Deal-source links
- canonical deal id
- candidate id
- source id
- snapshot id
- link type: discovery, verification, conflict, historical, rejected
- trust tier
- official source flag
- created at
- notes

### Score records
- canonical deal id
- scoring version
- scoring config hash
- estimated net value
- score 0-100
- score band
- recommended action
- score components JSON
- missing data warnings
- created at

### Run history
- run id
- run type
- start time
- end time
- status
- dry-run flag
- planned-run flag
- source counts
- snapshot counts
- candidate counts
- canonical counts
- conflict counts
- score counts
- digest path
- sanitized error summary
- created at

## Required behavior
- Persist candidates before canonicalization.
- Preserve source links after canonicalization.
- Create a new score record when scoring runs, rather than silently overwriting prior scores unless current code intentionally stores latest-only and docs say so.
- Link run history to snapshots/candidates/scores where practical.
- Support schema migration from existing local DB.
- Keep existing tests passing.

## Required tests
Tests should cover:
- migration applies on fresh DB
- migration applies on existing DB
- candidate insertion/retrieval
- source-link insertion/retrieval
- score record insertion/retrieval
- run history insertion/retrieval
- foreign key or relationship integrity where supported
- deterministic serialization for JSON fields

## Acceptance criteria
- Storage has explicit candidate, source-link, score, and run-history persistence.
- Existing flow writes these records or has a documented transitional gap.
- Docs/architecture reflect implemented tables.
- Tests cover migration and storage helpers.



---

## 10. Banking MVP 26: Add canonical financial product taxonomy and offer lifecycle state machine

## Objective
Create a canonical taxonomy and offer lifecycle state machine for all MVP financial offer types, including credit cards.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
The MVP now includes deposit accounts, brokerage bonuses, and credit card acquisition offers. These cannot remain loosely categorized strings forever. A canonical taxonomy and lifecycle state machine are required for reliable extraction, dedupe, scoring, alerts, review, and future UI filtering.

## Dependencies
- Depends on issue #2 schema.
- Depends on issue #6 canonicalization/change tracking.
- Depends on Banking MVP 17 credit card scope update.
- Should precede rules engine, query/service layer, and richer dashboard/API work.

## Instructions
Read in order:
1. `AGENTS.md`
2. existing data model/schema
3. extractor and canonicalization code
4. scoring and digest code
5. review CLI/status code
6. docs/architecture and issue map
7. this issue body
8. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required product taxonomy
Define canonical categories/subcategories for:

### Deposit/banking
- checking
- savings
- checking_savings_bundle
- money_market
- cd
- business_checking
- business_savings
- other_deposit

### Brokerage/investment account promotions
- brokerage_deposit_bonus
- brokerage_transfer_bonus
- ira_transfer_bonus
- robo_advisor_bonus
- other_brokerage

### Credit cards
- personal_credit_card
- business_credit_card
- cash_back_card
- travel_rewards_card
- airline_card
- hotel_card
- points_card
- miles_card
- secured_card if included only as a normal public offer type
- other_credit_card

### Offer shape
Support offer-shape classification:
- cash_bonus
- points_bonus
- miles_bonus
- statement_credit
- elevated_apy
- fee_waiver
- mixed_offer
- unknown

## Required lifecycle states
Implement or standardize states:
- discovered
- extracted
- candidate
- needs_review
- unverified
- third_party_only
- verified
- watchlisted
- interested
- dismissed
- active
- expiring_soon
- expired
- unavailable
- rejected
- duplicate
- superseded
- conflict_review
- archived

## Required state transition rules
Document and enforce basic transition constraints where practical:
- new extraction creates `candidate` or `needs_review`
- verified official evidence can move to `verified`
- expiration date can move active offers to `expiring_soon` or `expired`
- duplicate detection can move candidates to `duplicate`
- reviewer can dismiss, watchlist, or archive
- conflicts move to `conflict_review`
- rejected offers remain queryable for audit but do not appear as active recommendations

## Required CLI/config behavior
Update CLI filters and configs so users can filter by:
- category
- subcategory
- offer shape
- lifecycle state
- verification status
- personal vs business
- credit card vs deposit/brokerage

## Required tests
Tests should cover:
- taxonomy validation
- invalid category rejection or safe unknown fallback
- lifecycle transitions
- category filters
- credit-card category support
- deposit/brokerage category support
- backward compatibility with existing fixtures

## Acceptance criteria
- Taxonomy is canonical and documented.
- Lifecycle states are documented and used consistently.
- CLI/review/digest can filter or display taxonomy and state.
- Tests cover both banking and credit-card categories.



---

## 11. Banking MVP 27: Add eligibility and requirements rules engine for banking and credit card offers

## Objective
Implement a rules engine that models eligibility, requirements, and restrictions for deposit, brokerage, and credit card offers.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
Offer value depends heavily on requirements: direct deposit, minimum deposit, spend requirement, holding period, annual fee, state restrictions, business eligibility, targeted status, and expiration. These should be structured as rules, not buried in free-text notes.

## Dependencies
- Depends on issue #5 extraction.
- Depends on Banking MVP 25 persistence updates.
- Depends on Banking MVP 26 taxonomy/lifecycle.
- Should precede advanced scoring refinements and query/service layer.

## Instructions
Read in order:
1. `AGENTS.md`
2. storage schema/migrations
3. extractor output models
4. scoring engine
5. review CLI
6. docs/architecture and verification
7. this issue body
8. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required rule concepts
Create a structured representation for rules/requirements.

### Shared fields
- rule id
- canonical deal id or candidate id
- rule type
- rule value
- value unit/currency
- time window if applicable
- evidence link id or snapshot id
- confidence
- source id
- applies to category/subcategory
- required vs optional
- user-review-needed flag
- notes

### Deposit/brokerage rule types
- minimum opening deposit
- minimum balance
- direct deposit requirement
- qualifying deposit requirement
- transfer requirement
- holding period
- monthly fee
- fee waiver
- early closure fee
- account closure waiting period
- new customer only
- excluded prior customers
- state restrictions
- business eligibility
- promo code requirement
- branch/online channel restriction
- expiration date
- payout timing

### Credit card rule types
- minimum spend requirement
- spend window
- annual fee
- first-year annual fee waiver
- statement credit requirement
- authorized user requirement if relevant
- issuer restriction
- once-per-lifetime or prior-cardholder restriction where visible
- business-only requirement
- targeted offer requirement
- public offer marker
- application deadline/expiration
- bonus payout timing
- excluded product family if visible
- intro APR terms only as secondary rules

## Required behavior
- Extractors should populate rules when possible.
- Unknown rules should remain unknown; do not guess.
- Scoring should consume rules rather than parsing raw notes when possible.
- Review CLI should show critical rules and missing critical rules.
- Digest should warn when required rules are missing.
- Rules should link back to evidence where available.

## Required tests
Tests should cover:
- deposit direct deposit rule
- minimum balance rule
- holding period rule
- credit card minimum spend rule
- credit card spend window rule
- credit card annual fee rule
- state restriction rule
- targeted offer rule
- missing critical rule warning
- scoring consuming structured rules

## Acceptance criteria
- Requirements are represented structurally for banking and credit cards.
- Rule evidence links exist where evidence capture supports them.
- Scoring and review workflows use rules.
- Tests cover representative rule types.



---

## 12. Banking MVP 28: Add historical offer tracking and best-ever/typical/weak classification

## Objective
Add historical offer tracking so the system can understand whether a current banking or credit card offer is unusually strong, typical, weak, recurring, or stale.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
A $300 checking bonus, 100k-point credit card offer, or 5.00% APY promotion means more when compared to historical offers from the same institution/product. The MVP should preserve offer history and classify current offers against prior observed terms.

## Dependencies
- Depends on issue #6 change tracking.
- Depends on Banking MVP 25 persistence tables.
- Depends on Banking MVP 26 taxonomy/lifecycle.
- Depends on Banking MVP 30 credit card model/scoring for credit-card-specific historical values.

## Instructions
Read in order:
1. `AGENTS.md`
2. canonical deal/change event storage
3. score records
4. source evidence model
5. scoring engine
6. review/digest code
7. docs/architecture and verification
8. this issue body
9. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required historical concepts
Track:
- institution/issuer
- product/card/account name
- category/subcategory
- offer shape
- observed headline value
- estimated cash-equivalent value where available
- expiration date
- observed date range
- source ids
- official verification status
- key requirement snapshot
- score snapshot
- change event links

## Required classification
Implement transparent classification such as:
- best_seen
- above_typical
- typical
- below_typical
- weak
- unknown_history
- new_product
- recurring_offer
- stale_history

The classification should be conservative. If insufficient history exists, use `unknown_history`.

## Required comparison logic
For deposit/brokerage:
- compare bonus amount for same institution/product/category
- compare APY/rate for same product/category
- compare cash lockup requirements
- compare direct deposit or holding-period friction

For credit cards:
- compare points/miles/cash bonus against prior observed offers for same card
- compare spend requirement and spend window
- compare annual fee and first-year fee waiver
- compare statement credits when they materially affect value
- avoid overvaluing points/miles unless scoring assumptions define cash-equivalent value

## Required CLI/digest behavior
Update outputs to show:
- historical classification
- prior best observed offer
- current vs prior headline value
- current vs prior estimated value
- last seen date
- evidence/source count
- confidence/history warning

## Required tests
Tests should cover:
- first-seen offer -> unknown/new classification
- repeated offer -> recurring
- stronger deposit offer -> above_typical or best_seen
- weaker deposit offer -> weak/below_typical
- stronger credit-card points offer -> above_typical/best_seen
- lower credit-card cash offer -> weak/below_typical
- insufficient history -> unknown_history

## Acceptance criteria
- Historical offer records or change events support offer comparison.
- Classification is visible in CLI/digest.
- Tests cover banking and credit-card histories.
- Docs explain assumptions and limitations.



---

## 13. Banking MVP 29: Add APY and rate normalization for savings, money market, and CD offers

## Objective
Add APY/rate normalization and effective-value calculations for savings, money market, and CD offers.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
Not all banking deals are fixed signup bonuses. Savings, money market, and CD promotions often depend on APY, promotional rate period, minimum balance, maximum balance, term length, and baseline comparison. The MVP needs a rate-aware model so these offers can be compared sensibly with cash bonuses.

## Dependencies
- Depends on issue #2 storage/schema.
- Depends on issue #5 extraction.
- Depends on issue #7 scoring.
- Depends on Banking MVP 27 rules engine.
- Can run before or after historical tracking, but should integrate with it if present.

## Instructions
Read in order:
1. `AGENTS.md`
2. banking extractor and term models
3. scoring config and scoring engine
4. storage schema
5. docs/architecture and verification
6. this issue body
7. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required rate fields
Support structured extraction/storage for:
- APY
- interest rate if distinct from APY
- promotional APY
- base APY
- promotional period
- CD term length
- minimum balance
- maximum balance
- required new money amount
- balance tier
- account type
- rate expiration date if stated
- geographic restrictions
- source evidence

## Required normalization
Implement deterministic helpers for:
- percentage parsing
- APY normalization to decimal
- term length normalization to days/months
- balance amount parsing
- promotional period parsing
- simple expected value over a configured horizon
- incremental value versus configured baseline APY
- annualized vs term-limited value distinction

## Required scoring integration
Scoring should:
- estimate incremental interest value where enough data exists
- warn when term length or balance cap is missing
- penalize missing critical fields
- separate rate value from fixed cash bonus value
- avoid pretending a rate offer is a fixed cash bonus
- expose calculation assumptions in score explanation

## Required CLI/digest behavior
CLI/digest should show:
- APY/rate
- term length or promotional period
- min/max balance if known
- estimated incremental value
- missing rate terms
- freshness warning if rate evidence is stale

## Required tests
Tests should cover:
- APY parsing
- CD term parsing
- balance tier parsing
- incremental value calculation
- missing term warnings
- scoring explanation
- stale rate warning if freshness logic exists

## Acceptance criteria
- Savings/money market/CD offers can be represented as rate offers.
- Expected value is transparent and configurable.
- Tests prove rate normalization and scoring are deterministic.
- Docs explain limitations and assumptions.



---

## 14. Banking MVP 30: Add credit card offer model, extraction fields, and scoring framework

## Objective
Implement MVP support for credit card acquisition offers across schema, extraction, canonicalization, scoring, fixtures, review, and digest output.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
Credit cards are now part of the MVP. They require a distinct model from deposit/brokerage bonuses because value depends on bonus currency, minimum spend, spend window, annual fee, statement credits, eligibility restrictions, and offer type.

This issue should add credit-card support without applying for cards, submitting forms, or treating results as personalized financial advice.

## Dependencies
- Depends on Banking MVP 17 credit card scope docs.
- Depends on issue #2 storage/schema.
- Depends on issue #5 extraction.
- Depends on issue #6 canonicalization.
- Depends on issue #7 scoring.
- Depends on Banking MVP 26 taxonomy/lifecycle.
- Depends on Banking MVP 27 rules engine where possible.

## Instructions
Read in order:
1. `AGENTS.md`
2. `docs/architecture/banking-mvp.md`
3. `docs/issue-map.md`
4. storage/schema and migration files
5. extractor code
6. dedupe/canonicalization code
7. scoring engine/config
8. review CLI/digest code
9. fixture/test conventions
10. this issue body
11. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required credit card fields
Support fields for:
- issuer
- card name
- product family if visible
- personal vs business classification
- card network if visible
- offer title
- offer URL/source
- offer currency: cash, points, miles, statement credit, mixed
- headline bonus amount
- estimated cash-equivalent value
- point/mile valuation assumption id/config
- minimum spend requirement
- spend window
- annual fee
- first-year annual fee waiver
- statement credit amount
- statement credit requirements
- bonus payout timing
- offer expiration date
- targeted vs public offer
- eligibility/restriction notes
- source confidence
- evidence links
- missing critical fields

## Required extraction behavior
The extractor should identify credit-card offers from raw text fixtures and public-source snapshots.

Rules:
- Do not infer unstated values.
- Leave unknown fields unknown.
- Capture evidence spans for critical fields.
- Support cash, points, miles, statement credit, and mixed offers.
- Distinguish signup/acquisition offer from ordinary card benefits.
- Flag pages with no signup offer as non-deal.
- Flag targeted/private-language offers for review.

## Required canonicalization behavior
Canonicalization should match credit card offers using conservative signals:
- issuer
- card name
- offer currency
- headline bonus amount
- minimum spend requirement
- spend window
- annual fee
- expiration if known
- source URL/product page

Conflicts should be preserved, not overwritten.

## Required scoring behavior
Credit card scoring should compute:
- gross headline value
- estimated cash-equivalent value
- annual fee cost
- minimum spend friction penalty
- spend window pressure penalty
- targeted/restriction penalty
- missing data penalty
- verification/source-confidence adjustment
- final estimated net value
- score 0-100
- score band
- recommended action
- explanation

Scoring must be transparent and configurable. Do not hard-code opaque values for points/miles without a config and explanation.

## Required fixtures
Add realistic offline fixtures for:
- cash bonus card
- points bonus card
- miles bonus card
- statement credit card
- mixed bonus card
- business card
- targeted offer
- duplicate offer across sources
- conflicting minimum spend
- benefits-only non-deal page
- expired card offer

## Required CLI/digest behavior
Update commands and digest output so credit card offers can be:
- listed
- searched by issuer/card
- filtered by personal/business
- filtered by offer currency
- scored
- shown with key requirements
- flagged for review
- included in alert digest

## Required tests
Tests should cover:
- credit card extraction
- non-deal credit card page rejection
- canonicalization/dedupe
- conflict detection
- scoring
- digest inclusion
- CLI filtering
- missing critical fields

## Acceptance criteria
- Credit-card offers are first-class MVP deals.
- Credit-card fixture flow works offline.
- Critical fields are structured and evidence-backed where possible.
- Scoring is transparent and configurable.
- Existing deposit/brokerage behavior remains intact.



---

## 15. Banking MVP 31: Add conflict resolution policy and reviewer override audit log

## Objective
Add a conflict resolution policy and reviewer override audit log so contradictory terms, source disagreements, and manual corrections are handled safely and transparently.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
Financial offers often appear with conflicting terms across official pages, third-party blogs, newsletters, and outdated pages. The system needs explicit conflict handling instead of silently overwriting values. Manual corrections must be auditable because they affect ranking, review, and future UI display.

## Dependencies
- Depends on issue #6 change tracking.
- Depends on Banking MVP 20 evidence capture.
- Depends on Banking MVP 22 official-source verification.
- Depends on Banking MVP 25 persistence tables.
- Depends on Banking MVP 30 credit card model for credit-card conflicts.

## Instructions
Read in order:
1. `AGENTS.md`
2. canonicalization/change event code
3. evidence/linking code
4. review CLI/status workflow
5. scoring/digest code
6. storage schema
7. docs/architecture and verification
8. this issue body
9. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required conflict model
Track conflicts with:
- conflict id
- canonical deal id
- field name
- existing value
- new value
- existing source/evidence id
- new source/evidence id
- source trust comparison
- conflict type
- severity
- status
- created at
- resolved at
- reviewer notes

Conflict types should include:
- value_conflict
- expiration_conflict
- requirement_conflict
- eligibility_conflict
- source_trust_conflict
- stale_source_conflict
- official_vs_third_party_conflict
- credit_card_spend_requirement_conflict
- credit_card_bonus_amount_conflict
- apy_rate_conflict

## Required resolution policy
Implement transparent rules:
- official source beats third-party only when field meaning clearly matches
- newer source does not automatically beat official source
- conflicting expiration dates require review unless one source is clearly stale/expired
- missing value does not overwrite known value
- lower-confidence extraction does not overwrite higher-confidence reviewed value
- manual reviewer override takes precedence but must be auditable
- rejected/expired source evidence remains available for history

## Required audit log
Track reviewer actions:
- field override
- status change
- verification decision
- conflict resolution
- dismissal/rejection
- watchlist/interested status
- notes update

Audit fields:
- action id
- deal id
- field changed
- old value
- new value
- reason
- reviewer/source actor
- timestamp
- related conflict id
- related evidence id

## Required CLI behavior
Add or update commands:
- list conflicts
- show conflict detail
- resolve conflict
- override field with reason
- show audit history for deal
- show unresolved high-severity conflicts

Use existing CLI conventions if different.

## Required tests
Tests should cover:
- official vs third-party conflict
- stale source conflict
- credit card spend requirement conflict
- APY/rate conflict
- manual override audit
- missing value not overwriting known value
- unresolved conflicts triggering review/digest warnings

## Acceptance criteria
- Conflicts are persisted and visible.
- Manual overrides require notes/reason and are auditable.
- Scoring/digest can surface unresolved conflicts.
- Tests cover deposit, rate, and credit-card conflicts.



---

## 16. Banking MVP 32: Add query and service layer for future dashboard/API consumption

## Objective
Add a clean query/service layer that future UI, API, CLI, and automation workflows can use without directly coupling to raw SQLite tables.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
The eventual UI should sit on top of stable service/query functions, not scattered SQL or CLI-only logic. This issue should create the read/query boundary for canonical deals, sources, scores, evidence, alerts, and review state.

## Dependencies
- Depends on issue #2 storage/schema.
- Depends on issue #6 canonical deals.
- Depends on issue #7 scoring.
- Depends on issue #8 review workflow.
- Depends on Banking MVP 25 persistence tables.
- Depends on Banking MVP 26 taxonomy/lifecycle.
- Should precede full web dashboard work.

## Instructions
Read in order:
1. `AGENTS.md`
2. storage/repository modules
3. CLI commands
4. scoring/digest modules
5. taxonomy/lifecycle modules
6. docs/architecture and verification
7. this issue body
8. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required service/query capabilities
Create a service layer that supports:

### Deal discovery/search
- list canonical deals
- search by institution/issuer
- search by product/card/account name
- filter by category/subcategory
- filter by lifecycle state
- filter by verification status
- filter by offer currency
- filter by personal/business
- filter by minimum score
- filter by estimated value range
- filter by expiration window
- filter by missing critical fields
- filter by conflict status

### Deal detail
- get deal summary
- get structured terms/rules
- get latest score
- get source links
- get evidence links
- get status/audit history
- get conflicts
- get historical classification

### Source views
- list sources
- source health summary
- source coverage by category
- source detail with recent snapshots

### Alert/digest views
- get digest candidates
- get review-needed deals
- get expiring deals
- get high-value new deals
- get changed watched deals

## Required design constraints
- Keep the service layer independent from CLI presentation formatting.
- Return typed dataclasses/Pydantic models if the repo already uses them; otherwise use simple dataclasses/dicts consistently.
- Keep SQL isolated in repository/storage helpers.
- Make query functions deterministic and easy to test.
- Do not add a web server in this issue.

## Required tests
Tests should cover:
- search by institution/issuer
- credit card filtering
- deposit account filtering
- lifecycle/verification filters
- latest score retrieval
- evidence/source retrieval
- conflicts/audit retrieval
- deterministic ordering
- empty-result behavior

## Required docs
Document:
- intended service-layer usage
- supported filters
- examples for future UI/API integration
- non-goal: no hosted app/dashboard yet

## Acceptance criteria
- Query/service layer exists and is used by CLI where reasonable.
- Future dashboard can call service functions without raw SQL knowledge.
- Tests cover key filters and detail views.
- Docs explain the boundary.



---

## 17. Banking MVP 33: Add data export, import, backup, and restore workflow

## Objective
Add local export/import and backup/restore workflows so the MVP database, source registry, evidence metadata, and review history are portable and recoverable.

## Track
Track B: Deal Intelligence + Database Layer

## Product context
This is a local-first personal system. The database will accumulate source history, offer evidence, reviewer notes, score history, and audit logs over time. The user needs a safe way to back up, move, inspect, and restore data without corrupting the local store.

## Dependencies
- Depends on issue #2 storage/schema.
- Depends on Banking MVP 25 persistence tables.
- Depends on Banking MVP 31 audit log if available.
- Should be completed before any hosted UI or long-running scheduled usage.

## Instructions
Read in order:
1. `AGENTS.md`
2. storage configuration
3. migration code
4. repository/storage helpers
5. CLI code
6. docs/verification and architecture
7. this issue body
8. only files needed for this task

## Standard implementation contract
- Start from latest `origin/main`.
- Confirm the working tree is clean before editing.
- Create one issue-scoped branch named like `codex/<issue-number>-<short-slug>`.
- Implement only this issue's scope.
- Keep tests offline by default.
- Do not introduce browser automation, proxies, CAPTCHA bypassing, paywall bypassing, credentialed scraping, or private-session collection.
- Update docs when behavior, commands, schemas, config, or safety boundaries change.
- Run the relevant validation from `docs/verification.md`.
- Commit, push, and open a PR against `main`.
- Final response must include Summary, Files changed, Validation, Risks/follow-ups, and PR URL.


## Required export behavior
Support exports for:
- canonical deals
- deal terms/rules
- sources
- source health
- raw snapshot metadata
- evidence links
- score records
- status events
- change events
- conflicts
- audit log
- run history

Formats:
- JSON export for full fidelity
- CSV export for common human-readable views
- optional markdown summary for review if existing digest patterns make this easy

## Required import behavior
Support safe import for:
- full JSON backup restore
- source registry seed imports
- demo fixture imports
- optional CSV import only for well-defined views if practical

Import should:
- validate schema version
- avoid duplicate uncontrolled inserts
- preserve ids or map ids safely
- support dry-run validation
- report counts and errors
- never overwrite existing reviewer/audit data without explicit flag and documentation

## Required backup/restore commands
Add commands equivalent to:
- `pdi banking export --format json --output <path>`
- `pdi banking export --format csv --output <dir>`
- `pdi banking backup --output <path>`
- `pdi banking import --input <path> --dry-run`
- `pdi banking restore --input <path>`

Use existing CLI conventions if different.

## Required safety behavior
- Do not export secrets.
- Do not export private credentials.
- Sanitize or exclude sensitive personal data if any future fields exist.
- Make backups local files only.
- Do not send exports externally.
- Document where exports are written.

## Required tests
Tests should cover:
- JSON export round trip
- CSV export created
- dry-run import validation
- duplicate import behavior
- schema version mismatch
- corrupted file failure
- missing optional tables handled safely
- audit/review history preserved

## Acceptance criteria
- User can back up and restore local MVP data.
- Export/import works offline.
- Dry-run import validates safely.
- Docs explain backup/restore workflow.
- Tests cover happy path and failure cases.


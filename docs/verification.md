# Verification

This document defines validation expectations for the Banking MVP and the RepoOS-style AgentOps operating layer.

## Current state

The initial Python package, SQLite storage layer, source policy validator,
collector framework, deterministic banking extractor, conservative dedupe layer,
transparent banking scoring engine, local review CLI, local alert digest,
offline fixture smoke flow, and local run history exist. Storage validation is
available through pytest and the database initialization command.
Source policy validation is available through the `pdi.sources` module and
offline pytest coverage.
Collector validation is available through local-only pytest coverage under
`tests/collectors`. Extractor validation is available through offline fixture
coverage under `tests/extractors`. Dedupe validation is available through
offline fixture coverage under `tests/dedupe`. Scoring validation is available
through config validation and offline fixture coverage under `tests/scoring`.
Review CLI validation is available through offline fixture coverage under
`tests/cli`. Alert digest validation is available through `pdi.alerts` config
validation and offline fixture coverage under `tests/alerts`. Offline full-flow
smoke validation is available under `tests/integration`.

## Docs-only validation

For documentation-only changes, manually verify:

- Markdown renders cleanly.
- Internal links point to files that exist or are explicitly planned.
- Banking MVP scope is clear.
- Deferred categories are not accidentally included.
- Credit-card acquisition offers are in MVP scope and are not described as deferred.
- Safety boundaries are preserved.
- No docs instruct agents to circumvent source rules or collect from private sessions.
- No docs ask agents to store private auth material or highly sensitive personal identifiers.
- No docs instruct agents to apply for cards, submit forms, store full card numbers, store sensitive personal financial information, bypass anti-bot protections, bypass paywalls, bypass CAPTCHAs, or bypass access controls.
- Any command examples are labeled as expected/future if not yet implemented.
- GitHub Issue bodies are directly usable as implementation prompts and do not include a separate implementation-prompt section.
- Runner docs describe the organization-level `amanm02` self-hosted runner, not a repository-level runner, unless that changes.

Suggested manual checklist:

```text
README.md reviewed
AGENTS.md reviewed
MEMORY.md reviewed
docs/issue-map.md reviewed
docs/verification.md reviewed
docs/architecture/banking-mvp.md reviewed
docs/decisions.md reviewed
docs/agentops/ reviewed
docs/prompt-library.md reviewed
docs/release-checklists/banking-mvp.md reviewed
docs/roadmap/ reviewed
```

## Setup validation

The development setup is:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

If the implementation chooses another package manager, update this file and README together.

## GitHub Actions runners

Product CI uses GitHub-hosted `ubuntu-latest` runners. AgentOps GitHub Actions
remain separate and use the organization-level self-hosted runner from the
`amanm02` organization with selector `[self-hosted, macOS, ARM64]`.

The organization runner must be made available to `amanm02/PersonalDealIntelligence` through organization runner access settings and must have all three labels. See `docs/agentops/github-actions-runners.md`.

If `gh workflow list --all` reports `AgentOps` as `disabled_manually`, do not
claim AgentOps CI coverage from the PR check rollup. Re-enable the workflow only
after `main` contains the current runner-safe AgentOps workflow.

AgentOps currently uses the self-hosted runner's existing `python3` rather than
`actions/setup-python`. Failed runs on June 20, 2026 showed `setup-python`
failing while creating `/Users/runner` on the self-hosted macOS runner. Treat
that symptom as runner/toolcache setup, not Product CI failure.

## AgentOps tooling validation

Validate AgentOps workflow hygiene locally with:

```bash
make workflow-hygiene
make agentops-test
python3 -m pytest tests/agentops -q
python3 -m tools.agentops.check_work_state || true
python3 -m tools.agentops.check_work_state --advisory
python3 -m tools.agentops.check_work_state --expected-issue <ISSUE_NUMBER> || true
python3 -m tools.agentops.summarize_ci_failure --help
python3 -m tools.agentops.recommend_next_issue
```

Use `python3 -m tools.agentops.check_issue_map_freshness --fixture <path>` for
offline issue-status comparisons, or `--github` only when live GitHub access is
explicitly intended.

Use `python3 -m tools.agentops.check_pr_body --body-file <path>` before PR
creation, or `--github-pr <number>` for an existing PR when GitHub access is
explicitly intended.

Use `docs/agentops/github-codex-runbook.md` when GitHub CLI, network approval,
PR publishing, or Codex thread inspection behavior is ambiguous.

## Product CI validation

The product CI workflow mirrors these local commands:

```bash
python3 -m pdi.sources validate --config config/banking_sources.yaml
python3 -m pdi.scoring validate --config config/banking_scoring.yaml
python3 -m pdi.alerts validate --config config/banking_alerts.yaml
python3 -m pytest
```

## Test validation

Current narrower source policy command:

```bash
python3 -m pytest tests/sources
```

Current narrower collector command:

```bash
python3 -m pytest tests/collectors
```

Current narrower extractor command:

```bash
python3 -m pytest tests/extractors
```

Current narrower stored-snapshot re-extraction commands:

```bash
python3 -m pytest tests/extractors tests/storage tests/cli
python3 -m pdi --db /tmp/pdi-reextract.sqlite banking reextract --all --dry-run --format json
```

Current narrower dedupe command:

```bash
python3 -m pytest tests/dedupe
```

Current narrower scoring command:

```bash
python3 -m pytest tests/scoring
```

Current narrower review CLI command:

```bash
python3 -m pytest tests/cli
```

Current narrower alert digest command:

```bash
python3 -m pdi.alerts validate --config config/banking_alerts.yaml
python3 -m pytest tests/alerts
```

Current narrower credit-card CLI and digest display command:

```bash
python3 -m pdi.alerts validate --config config/banking_alerts.yaml
python3 -m pytest tests/cli tests/alerts tests/integration
python3 scripts/check_banking_demo.py
```

Current narrower offline integration command:

```bash
python3 -m pytest tests/integration
```

Current narrower run history command:

```bash
python3 -m pytest tests/storage tests/cli tests/integration
```

Current demo readiness command:

```bash
python3 scripts/check_banking_demo.py
```

## Source policy validation

Validate the source registry with:

```bash
python3 -m pdi.sources validate --config config/banking_sources.yaml
python3 -m pdi --db /tmp/pdi-public-pilot.sqlite banking sources validate
python3 -m pdi --db /tmp/pdi-public-pilot.sqlite banking sources list
python3 -m pdi --db /tmp/pdi-public-pilot.sqlite banking sources show seed-issuer-credit-card-detail
python3 -m pdi --db /tmp/pdi-public-pilot.sqlite banking sources onboarding-check --review-required
python3 -m pdi --db /tmp/pdi-public-pilot.sqlite banking sources scaffold \
  --id seed-new-card-source \
  --name "Seed New Card Source" \
  --publisher "Example Issuer" \
  --url "https://example.test/card" \
  --source-type official_promo_page \
  --source-class official \
  --subcategory credit_card_signup_bonus
python3 -m pytest tests/sources tests/cli
```

The source registry should include source class, trust tier, official-source
status, deposit/brokerage/credit-card coverage flags, fixture enablement, source
priority, region scope, compliance notes, and safe disabled or fixture-only
defaults for new source-universe placeholders.
Source onboarding checks should surface missing policy fields, pending review
status, and live-collection blockers. Source scaffolds must print disabled or
fixture-only YAML and must not edit `config/banking_sources.yaml` directly.

Validate the reusable offline demo source seed pack with:

```bash
python3 -m pdi.sources validate --config config/banking_sources.demo.yaml
python3 -m pytest tests/collectors/test_demo_corpus.py tests/integration/test_demo_corpus_flow.py
```

Validate the opt-in public-pilot path with:

```bash
python3 -m pdi --db /tmp/pdi-public-pilot.sqlite banking run --dry-run --sources public-pilot
python3 -m pdi --db /tmp/pdi-public-pilot-29a.sqlite banking run --dry-run --sources public-pilot --format json
python3 -m pytest tests/sources tests/collectors tests/cli tests/integration
```

Public-pilot tests are offline and deterministic. Checked-in public-pilot
sources are disabled by default; dry-run never fetches network content, and live
RSS collection requires an enabled, policy-valid local source config,
`--confirm-live`, and the bounded safe fetcher checks.

## Scoring config validation

Validate banking scoring assumptions with:

```bash
python3 -m pdi.scoring validate --config config/banking_scoring.yaml
```

## Alert config validation

Validate banking alert rules with:

```bash
python3 -m pdi.alerts validate --config config/banking_alerts.yaml
```

## Run history validation

Validate dry-run behavior, recent run listing, and run inspection with a fresh
temporary database:

```bash
rm -f /tmp/pdi-banking-run.sqlite /tmp/pdi-banking-run-digest.md
python3 -m pdi --db /tmp/pdi-banking-run.sqlite banking run --dry-run --digest-output /tmp/pdi-banking-run-digest.md --as-of 2026-06-18 --format json
python3 -m pdi --db /tmp/pdi-banking-run.sqlite banking runs --format json
python3 -m pdi --db /tmp/pdi-banking-run.sqlite banking run-status "$(python3 -m pdi --db /tmp/pdi-banking-run.sqlite banking runs --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')" --format json
```

Validate persistent execution only when durable local workflow writes are
intended:

```bash
rm -f /tmp/pdi-banking-run-execute.sqlite /tmp/pdi-banking-run-execute-digest.md
python3 -m pdi --db /tmp/pdi-banking-run-execute.sqlite banking run --execute --digest-output /tmp/pdi-banking-run-execute-digest.md --as-of 2026-06-18 --format json
```

## Demo search validation

Issues #14 and #15 add a realistic offline demo corpus and product-facing
banking deal find/search behavior. Validate the reusable local corpus and local
search behavior with:

```bash
python3 -m pdi.sources validate --config config/banking_sources.demo.yaml
python3 -m pytest tests/collectors/test_demo_corpus.py tests/integration/test_demo_corpus_flow.py
python3 -m pytest tests/integration/test_qa_benchmark.py
python3 -m pdi --db /tmp/pdi-banking-smoke.sqlite banking smoke-test \
  --digest-output /tmp/pdi-banking-smoke-digest.md \
  --as-of 2026-06-18 \
  --reset-db
python3 -m pdi --db /tmp/pdi-demo-qa.sqlite banking qa-benchmark --reset-db
python3 -m pdi --db /tmp/pdi-demo-qa.sqlite banking qa-benchmark --reset-db --json
python3 -m pdi --db /tmp/pdi-banking-smoke.sqlite banking find --query "checking bonus"
python3 -m pdi --db /tmp/pdi-banking-smoke.sqlite banking find --subcategory brokerage_bonus --min-bonus 500
```

Issue #16 added the fresh-clone demo readiness gate. Keep the README, release
checklist, and this file aligned whenever the demo path changes.

The QA benchmark is deterministic and offline-only. It validates the reusable
demo corpus for expected deal coverage, duplicate merging, conflict surfacing,
non-deal suppression, score sanity, expired and low-value handling, ambiguous
terms, and fixture edge-case coverage. Supported regression-gate checks are
reported in deterministic order with `status`, `actual`, `expected`, and
`reason`; failed supported checks set `verification_status` to `fail`, make CLI
execution return nonzero, and appear in the top-level `failures` list.
Credit-card runtime coverage is reported as `pending_runtime` with a
deterministic reason code until 24D adds that benchmark coverage. Future-only
systems such as evidence expansion, persistence expansion, taxonomy/lifecycle,
and rules-engine checks are reported as `skipped_dependency` sections with
machine-readable `reason_code` values rather than failures. Pending and skipped
sections are visible but non-blocking.
Deposit and brokerage fixture scenarios are identified by stable
`scenario_ids` in `examples/demo_banking/manifest.yaml`; current expected
scenarios include active checking, active savings, checking+savings bundle,
brokerage bonus, CD or money-market style offer, expired offer, duplicate
offer, conflicting terms, low-value offer, ambiguous terms,
disabled/disallowed source, and non-deal content. `qa-benchmark --json`
reports these under `scenario_coverage`.

## Banking MVP readiness validation

For Banking MVP release-readiness hardening, run the exact current validation
suite below. Use `python3 -m pdi` for CLI validation so the command exercises
the package entrypoint without depending on an installed console script.

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
python3 -m pdi --db /tmp/pdi-demo-qa.sqlite banking qa-benchmark --reset-db --json
```

## Expected future quality checks

If configured, run:

```bash
ruff check .
ruff format --check .
mypy .
```

If a different linter/type checker is selected, update this file.

## Offline test requirement

Tests should not make live network calls by default.

Use local fixtures for:

- source config validation
- raw snapshot collection
- RSS/email/manual text parsing
- extraction
- dedupe
- scoring
- CLI output
- digest rendering
- full offline smoke flow

Any live integration test must be opt-in, clearly named, and disabled by default.

## Banking MVP validation by layer

### Source policy

Must validate when implemented:

- required fields exist
- unknown or unsafe fields are rejected
- unsafe combinations are rejected
- collection frequency limits are parseable
- enabled sources are explicitly approved
- method-specific allow flags match the collection method
- source scopes stay inside Banking MVP categories and subcategories
- private-access sources fail closed unless a future issue explicitly defines a compliant user-authorized flow

### Storage

Must validate:

- database initializes from scratch
- mock banking deals can be inserted and queried
- raw snapshots link to extracted/canonical records
- raw snapshot content hashes are derived from stored raw text
- duplicate raw snapshot content hashes are queryable without deduping rows
- `banking_deal_candidates` is the canonical extracted pre-dedupe candidate
  table; helpers preserve unknown terms as nulls, deterministic JSON evidence,
  rejected filters, pending filters, canonicalization status filters, and raw
  snapshot foreign-key integrity
- existing candidate rows migrate cleanly from older local database versions
- `banking_deal_source_links` is the canonical deal-to-candidate/snapshot
  evidence relation; helpers list by deal and candidate, preserve nullable
  unknown source authority and review metadata, avoid duplicate relationship
  rows, and enforce source-link foreign-key integrity
- stored raw snapshots can be re-extracted offline without live collection
- re-extraction dry-run reports deterministic candidate comparisons without
  writing new candidate rows
- re-extraction write mode creates new pre-dedupe candidates while preserving
  reviewed canonical deal values and statuses
- field-level evidence links preserve deal, candidate, raw snapshot, source-link,
  field, extracted value, excerpt, span, confidence, and extraction metadata
- missing field evidence is detectable for populated canonical fields
- status/change events can be recorded
- partially extracted unknown fields remain null

### Collectors

Must validate when implemented:

- manual text fixtures work
- RSS fixtures work
- disallowed sources are blocked
- content hashes are stable
- no tests require internet access
- login-required HTML collection is blocked
- high-frequency collection is blocked when last collection metadata is too recent
- collected snapshots can persist to `raw_deal_snapshots`

### Extraction

Must validate when implemented:

- checking bonus fixture parses correctly
- savings bonus fixture parses correctly
- brokerage bonus fixture parses correctly
- credit-card acquisition fixtures parse issuer, card name, offer currency,
  headline value, minimum spend, spend window, annual fee, public/targeted
  classification, and evidence when credit-card extraction is implemented
- benefits-only credit-card pages are rejected or low confidence when
  credit-card extraction is implemented
- missing high-impact fields stay unknown
- non-deal content is rejected or low confidence
- evidence spans are preserved when available

### Dedupe and canonicalization

Must validate when implemented:

- exact duplicates merge
- strong matches merge conservatively
- conflicts are preserved
- low-confidence data does not overwrite higher-confidence data silently
- change events are recorded

### Scoring

Must validate when implemented:

- scoring is deterministic for fixed config
- net value accounts for fees and cash lockup
- missing data creates warnings
- expired deals are handled
- config changes affect outputs predictably
- credit-card scoring explains cash-equivalent value, annual fee, minimum spend
  friction, spend-window pressure, missing data, source confidence, and
  valuation assumptions when credit-card scoring is implemented

### CLI/review workflow

Must validate when implemented:

- list filters work
- show output includes terms, score, source references, field-level evidence,
  snapshot hashes, and missing-evidence warnings
- status updates create events
- review-needed surfaces conflicts/missing data
- expiring filter works
- search/find free-text and structured filters work
- search/find results are ranked by score, net value, bonus amount, and deal id
- search/find JSON includes match reason and source fields

### Digest

Must validate when implemented:

- high-priority deals appear
- low-priority deals are suppressed from high-priority sections
- expiring deals appear
- changed watched/interested deals appear
- output is deterministic for fixed fixture data
- configured notification channels are disabled or dry-run by default and do not
  send external messages

### Offline fixture smoke flow

Must validate:

- local fixtures produce raw snapshots
- extracted candidates are persisted
- non-deal fixtures are rejected
- duplicate sample deals canonicalize conservatively
- conflicting sample deals are marked for review
- canonical deals are scored
- markdown digest artifact is generated locally
- no live network, browser automation, external messages, email account access,
  or banking actions are required

### Demo readiness

Must validate:

- fresh setup instructions are copy/pasteable
- `pdi banking demo --reset --seed fixtures` initializes a clean local database
- `pdi banking find` returns ranked checking, savings, and brokerage demo deals
- find results include score/net value context, match reason, needs-review
  state, and source label or URL
- `pdi banking show <deal_id>` displays terms, credit-card acquisition terms
  when present, evidence/source references, missing-data warnings, and status
- `pdi banking digest --demo` writes a local artifact
- `pdi banking qa-benchmark --reset-db` reports pass/fail coverage for expected
  demo deals, duplicate/conflict behavior, non-deal suppression, score sanity,
  and local fixture edge cases
- the demo path is deterministic across reset runs
- no live network, external notification send, credential, personal identifier,
  or financial-action step is required

### Run history

Must validate:

- dry-run mode works
- dry-run updates only run history in the real database
- dry-run does not create the durable digest artifact
- `--execute` is required for persistent workflow writes
- run records are persisted
- overlapping runs are blocked
- failed runs release the lock after failure state is persisted
- recent run listing works
- one run can be inspected

## Final response validation reporting

Agent final responses must include exact commands and results, for example:

```text
Validation
- python3 -m pytest tests/storage - passed
- make agentops-pr - passed
```

If validation could not be run:

```text
Validation
- Not run: <reason>.
- Manual docs review completed for <files>.
```

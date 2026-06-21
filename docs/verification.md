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
- Safety boundaries are preserved.
- No docs instruct agents to circumvent source rules or collect from private sessions.
- No docs ask agents to store private auth material or highly sensitive personal identifiers.
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
python3 -m pytest tests/alerts
```

Current narrower offline integration command:

```bash
python3 -m pytest tests/integration
```

Current narrower run history command:

```bash
python3 -m pytest tests/storage tests/cli tests/integration
```

## Source policy validation

Validate the source registry with:

```bash
python3 -m pdi.sources validate --config config/banking_sources.yaml
```

Validate the reusable offline demo source seed pack with:

```bash
python3 -m pdi.sources validate --config config/banking_sources.demo.yaml
python3 -m pytest tests/collectors/test_demo_corpus.py tests/integration/test_demo_corpus_flow.py
```

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

## Planned demo readiness validation

Issues #14, #15, and #16 are expected to add a realistic offline demo corpus,
product-facing banking deal find/search behavior, and a fresh-clone demo gate.
Issue #14 adds the reusable local corpus and source seed pack only. Until #15
and #16 implement and validate the remaining commands, treat those examples as
planned validation shape, not current CLI guarantees:

```bash
python3 -m pdi.sources validate --config config/banking_sources.demo.yaml
python3 -m pdi --db /tmp/pdi-banking-demo.sqlite banking find --query "checking bonus"
python3 -m pdi --db /tmp/pdi-banking-demo.sqlite banking find --subcategory brokerage_bonus --min-bonus 500
python3 -m pdi --db /tmp/pdi-banking-demo.sqlite banking digest --output /tmp/pdi-banking-demo-digest.md
python3 scripts/check_banking_demo.py
```

Any final implementation may choose equivalent command names, but the README,
release checklist, and this file must be updated together when that happens.

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

### CLI/review workflow

Must validate when implemented:

- list filters work
- show output includes terms and score
- status updates create events
- review-needed surfaces conflicts/missing data
- expiring filter works

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

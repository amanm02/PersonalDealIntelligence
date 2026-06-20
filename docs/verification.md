# Verification

This document defines validation expectations for the Banking MVP.

## Current state

The initial Python package, SQLite storage layer, source policy validator,
collector framework, deterministic banking extractor, conservative dedupe layer,
and transparent banking scoring engine exist. Storage validation is available
through pytest and the database initialization command. Source policy validation
is available through the `pdi.sources` module and offline pytest coverage.
Collector validation is available through local-only pytest coverage under
`tests/collectors`. Extractor validation is available through offline fixture
coverage under `tests/extractors`. Dedupe validation is available through
offline fixture coverage under `tests/dedupe`. Scoring validation is available
through config validation and offline fixture coverage under `tests/scoring`.

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

Suggested manual checklist:

```text
README.md reviewed
AGENTS.md reviewed
docs/issue-map.md reviewed
docs/verification.md reviewed
docs/architecture/banking-mvp.md reviewed
docs/decisions.md reviewed
docs/prompt-library.md reviewed
docs/release-checklists/banking-mvp.md reviewed
```

## Setup validation

The development setup is:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

If the implementation chooses another package manager, update this file and README together.

## Test validation

Current test command:

```bash
python3 -m pytest
```

Current narrower storage command:

```bash
python3 -m pytest tests/storage
```

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

Expected narrower commands as future modules are added:

```bash
python3 -m pytest tests/cli
python3 -m pytest tests/alerts
python3 -m pytest tests/integration
```

## Storage initialization validation

Validate database initialization and fictional fixture loading with:

```bash
python3 -m pdi.storage init --db /tmp/pdi-issue2.sqlite --seed-fixture examples/banking_deals.json
```

## Source policy validation

Validate the source registry with:

```bash
python3 -m pdi.sources validate --config config/banking_sources.yaml
```

## Scoring config validation

Validate banking scoring assumptions with:

```bash
python3 -m pdi.scoring validate --config config/banking_scoring.yaml
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

Any live integration test must be opt-in, clearly named, and disabled by default.

## Banking MVP validation by layer

### Source policy

Must validate:

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

Must validate:

- manual text fixtures work
- RSS fixtures work
- disallowed sources are blocked
- content hashes are stable
- no tests require internet access
- login-required HTML collection is blocked
- high-frequency collection is blocked when last collection metadata is too recent
- collected snapshots can persist to `raw_deal_snapshots`

### Extraction

Must validate:

- checking bonus fixture parses correctly
- savings bonus fixture parses correctly
- brokerage bonus fixture parses correctly
- missing high-impact fields stay unknown
- non-deal content is rejected or low confidence
- evidence spans are preserved when available

### Dedupe and canonicalization

Must validate:

- exact duplicates merge
- strong matches merge conservatively
- conflicts are preserved
- low-confidence data does not overwrite higher-confidence data silently
- change events are recorded

### Scoring

Must validate:

- scoring is deterministic for fixed config
- net value accounts for fees and cash lockup
- missing data creates warnings
- expired deals are handled
- config changes affect outputs predictably

### CLI/review workflow

Must validate:

- list filters work
- show output includes terms and score
- status updates create events
- review-needed surfaces conflicts/missing data
- expiring filter works

### Digest

Must validate:

- high-priority deals appear
- low-priority deals are suppressed from high-priority sections
- expiring deals appear
- changed watched/interested deals appear
- output is deterministic for fixed fixture data

### Run history

Must validate:

- dry-run mode works
- run records are persisted
- overlapping runs are blocked
- recent run listing works

## Final response validation reporting

Codex final responses must include exact commands and results, for example:

```text
Validation
- pytest tests/scoring - passed
- ruff check . - passed
```

If validation could not be run:

```text
Validation
- Not run: no Python package/test stack exists yet.
- Manual docs review completed for README.md and docs/verification.md.
```

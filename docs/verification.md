# Verification

This document defines validation expectations for the Banking MVP.

## Current state

Runtime implementation has not started yet. Until a package/test stack exists, validation is documentation-focused.

## Docs-only validation

For documentation-only changes, manually verify:

- Markdown renders cleanly.
- Internal links point to files that exist or are explicitly planned.
- Banking MVP scope is clear.
- Deferred categories are not accidentally included.
- Safety boundaries are preserved.
- No docs instruct agents to bypass bot protection, CAPTCHA, login restrictions, or source access controls.
- No docs ask agents to store sensitive financial identifiers.
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

## Expected future setup validation

Once Python packaging exists, expected setup validation is:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

If the implementation chooses another package manager, update this file and README together.

## Expected future test validation

Expected test command:

```bash
pytest
```

Expected narrower commands after modules exist:

```bash
pytest tests/storage
pytest tests/sources
pytest tests/collectors
pytest tests/extractors
pytest tests/dedupe
pytest tests/scoring
pytest tests/cli
pytest tests/alerts
pytest tests/integration
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
- unsafe combinations are rejected
- collection frequency limits are parseable
- login-required sources are not collected by unsafe collectors

### Storage

Must validate:

- database initializes from scratch
- mock banking deals can be inserted and queried
- raw snapshots link to extracted/canonical records
- status/change events can be recorded

### Collectors

Must validate:

- manual text fixtures work
- RSS fixtures work
- disallowed sources are blocked
- content hashes are stable
- no tests require internet access

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

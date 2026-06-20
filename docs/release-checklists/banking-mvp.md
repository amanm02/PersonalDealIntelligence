# Banking MVP Release Checklist

Use this checklist before treating the Banking MVP as usable for personal deal tracking.

## 1. Scope check

- [ ] Banking remains the only active MVP category.
- [ ] Clothing, travel, flights, hotels, cashback stacking, and browser extension work are deferred.
- [ ] README reflects the current implementation.
- [ ] `docs/issue-map.md` reflects current issue status.

## 2. Local setup

- [ ] Fresh clone works.
- [ ] Virtual environment setup works.
- [ ] Dependencies install successfully.
- [ ] No `.env.example` is required unless future external integrations add environment variables.
- [ ] No real secrets are committed.

## 3. Source policy validation

- [ ] Source config exists.
- [ ] Required fields are validated.
- [ ] Unsafe source configurations are rejected.
- [ ] Collection methods are explicit.
- [ ] Frequency limits are configured.
- [ ] Private-access sources fail closed unless a compliant user-authorized flow is explicitly added later.

## 4. Storage validation

- [ ] Database initializes from scratch.
- [ ] Raw snapshots can be stored.
- [ ] Extracted candidates can be stored.
- [ ] Canonical deals can be stored.
- [ ] Terms and restrictions can be stored.
- [ ] Status events can be stored.
- [ ] Change events can be stored.
- [ ] Run history can be stored if implemented.

## 5. Offline fixture pipeline

- [ ] Fixture command runs without internet access.
- [ ] Checking bonus fixture is processed.
- [ ] Savings bonus fixture is processed.
- [ ] Brokerage bonus fixture is processed.
- [ ] Duplicate fixture is deduped.
- [ ] Conflicting fixture is marked for review.
- [ ] Low-value fixture is suppressed from high-priority digest sections.
- [ ] Expired fixture is handled.
- [ ] Non-deal fixture is rejected or low-confidence.

## 6. Extraction sanity checks

- [ ] Bonus amount extraction works.
- [ ] Direct deposit terms extract when present.
- [ ] Minimum deposit/balance terms extract when present.
- [ ] Holding period extracts when present.
- [ ] Monthly fee extracts when present.
- [ ] Expiration date extracts when present.
- [ ] State restrictions extract when present.
- [ ] Missing high-impact terms remain unknown.
- [ ] Evidence spans or source references are preserved where possible.

## 7. Dedupe and conflict checks

- [ ] Exact duplicates merge.
- [ ] Strong duplicate candidates merge conservatively.
- [ ] Similar but different deals are not falsely merged.
- [ ] Conflicting high-impact fields create review-needed state.
- [ ] Material changes create change events.
- [ ] Lower-confidence data does not silently overwrite higher-confidence data.

## 8. Scoring sanity checks

- [ ] Gross bonus value is included.
- [ ] Monthly fees reduce estimated net value.
- [ ] Cash lockup opportunity cost is included.
- [ ] Direct deposit friction is reflected.
- [ ] Missing data creates warnings or penalties.
- [ ] Expired deals are handled.
- [ ] Recommended actions are explainable.
- [ ] Scores are deterministic for fixed config.

## 9. Review workflow

- [ ] User can list deals.
- [ ] User can inspect one deal.
- [ ] User can filter by status.
- [ ] User can filter by institution or subcategory.
- [ ] User can update deal status.
- [ ] Status updates create event records.
- [ ] Review-needed command surfaces conflicts and missing critical terms.
- [ ] Expiring deals can be listed.

## 10. Digest generation

- [ ] Markdown digest generates locally.
- [ ] Optional JSON digest generates if implemented.
- [ ] High-priority deals appear.
- [ ] Low-priority deals are suppressed from high-priority sections.
- [ ] Expiring deals appear.
- [ ] Changed watched/interested deals appear.
- [ ] Review-needed deals appear.
- [ ] Digest includes deal IDs for CLI follow-up.

## 11. Run history and dry-run

- [ ] Deferred to Issue #12; do not treat as Banking MVP release-blocking until implemented.
- [ ] When implemented, dry-run command works.
- [ ] When implemented, one-shot run command works.
- [ ] When implemented, run records include start/end/status/counts/errors/digest path.
- [ ] When implemented, overlapping runs are blocked.
- [ ] When implemented, recent runs can be listed.
- [ ] When implemented, one run can be inspected.

## 12. Safety and privacy review

- [ ] No private auth material is collected.
- [ ] Highly sensitive personal identifiers stay out of project storage.
- [ ] Financial actions, applications, enrollment, and money movement stay under direct user control.
- [ ] Source collection follows explicit source policies.
- [ ] Private-session data is not collected by automated source flows.
- [ ] Source access workarounds are not part of the implementation.
- [ ] Docs state that final terms must be verified on official institution pages.

## 13. Validation commands

Before release, run the full validation suite listed in `docs/verification.md`.

Current Banking MVP readiness commands:

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

Expected future quality commands, only after they are configured in the repo:

```bash
ruff check .
ruff format --check .
mypy .
```

## 14. Known limitations to document

- [ ] Extraction is imperfect and may miss nuanced terms.
- [ ] Scoring is based on configurable assumptions, not financial advice.
- [ ] Source coverage is limited by configured sources.
- [ ] User must verify final offers manually.
- [ ] Live source collection, if added later, must remain source-policy controlled.
- [ ] Run history and dry-run orchestration are deferred to Issue #12.

## Release decision

Do not consider the Banking MVP ready until:

- core validation passes
- fixture smoke flow works
- docs match implementation
- safety boundaries are intact
- known limitations are documented

# Future Categories

This file tracks deal categories that are intentionally deferred until the Banking MVP is complete and stable.

## Status

Deferred. Do not implement these categories as part of the Banking MVP.

## Deferred categories

### Credit card offers

Possible future scope:

- sign-up bonus tracking
- annual fee handling
- simple points/cash value assumptions
- issuer eligibility rules
- application timing reminders

Keep this separate from Banking MVP unless explicitly promoted into a post-MVP issue.

### Cashback stack optimization

Possible future scope:

- portal rate tracking
- card-linked offer stacking
- coupon stacking
- gift card stacking
- retailer exclusions

### Retail and clothing deals

Possible future scope:

- retailer watchlists
- price-drop monitoring
- size/color availability
- return-window tracking
- brand exclusions

### Travel deals

Possible future scope:

- destination watchlists
- hotel promotions
- flight fare alerts
- package deals
- transfer bonus tracking

### Flights

Possible future scope:

- route watchlists
- fare-history snapshots
- award availability research
- schedule and cabin filters

### Hotels

Possible future scope:

- hotel promotion tracking
- loyalty status benefits
- free-night certificate reminders
- destination/property watchlists

## Promotion rules

A future category can move into active implementation only when:

- Banking MVP release checklist is complete.
- The category has a scoped architecture note or PRD.
- Source and privacy boundaries are defined.
- Test fixtures exist before live source work.
- A GitHub Issue has clear acceptance criteria and validation.

The issue body should be directly usable as the implementation prompt. Do not include a separate `Codex prompt` section.

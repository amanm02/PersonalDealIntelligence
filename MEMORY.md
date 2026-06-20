# MEMORY.md

This file stores durable repo memory for agents. It is not a diary and must not contain transient task notes.

## Current repo facts

- This repository builds Personal Deal Intelligence.
- The initial product scope is the Banking MVP only.
- The architecture is local-first and currently uses Python, SQLite, stdlib `sqlite3`, and versioned SQL migrations.
- Current validation is offline by default and centered on `python3 -m pytest`.
- Source collection must be policy-driven before collector code uses a source.
- Banking terms with missing or ambiguous evidence must remain unknown rather than guessed.
- AgentOps infrastructure is process and repository-operating support; it is not product behavior.

## Known constraints

- Do not add live source collection unless a future issue explicitly defines the compliant source policy and disabled-by-default validation path.
- Do not add browser automation, private-session collection, source-access workarounds, financial-action automation, applications, enrollment, or money movement.
- Do not store secrets, credentials, private customer data, private auth material, or highly sensitive personal identifiers.
- Keep tests deterministic and offline by default.
- Keep `AGENTS.md` short and map-like.
- Keep `MEMORY.md` durable and non-duplicative.
- Do not create unbounded autonomous loops; self-improvement loops must be bounded, reviewable, and test-gated.

## Repeated agent mistakes

Use this format when a mistake repeats:

```md
### Mistake: <name>
- Observed behavior:
- Correct behavior:
- Prevention mechanism:
- Related files:
```

## Recently changed conventions

Use this format:

```md
### <YYYY-MM-DD> - <change>
- Change:
- Reason:
- Files affected:
```

## Deprecated guidance

Use this format:

```md
### Deprecated: <guidance>
- Replacement:
- Removal date:
- Cleanup issue:
```

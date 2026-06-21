## Summary

-

## Linked issue

- Closes #

## Dependency status

- [ ] Independent; can merge in any order.
- [ ] Depends on issue/PR:
- [ ] Must merge before issue/PR:

## Owned files

Files intentionally changed by this PR:

-

## Blocked files

Files intentionally avoided because another agent/PR owns them:

-

## Concurrency risk

- [ ] Low; no expected overlap with active work.
- [ ] Medium/high; overlap details and reviewer guidance:

## Merge gate

- [ ] Ready to review
- [ ] Needs remediation
- [ ] Blocked by dependency
- [ ] Blocked by conflict
- [ ] Safe to merge after checks pass

## Files changed

-

## Docs update

- [ ] I updated docs if behavior, structure, commands, tools, hooks, MCPs, runners, or workflows changed.
- [ ] Not applicable; this change does not affect docs.

## AgentOps checklist

- [ ] I updated `MEMORY.md` only for durable repo facts or repeated failure patterns.
- [ ] I updated the relevant registry if tools, functions, MCPs, hooks, skills, or workflows changed.
- [ ] I ran the required verification command.
- [ ] I added or updated tests/evals for repeated defects when applicable.
- [ ] I checked for stale or duplicate docs.
- [ ] I kept the diff small and reviewable.

## Validation commands and exact results

Paste each command run and its exact result. Use `not run` with a reason when a check is intentionally skipped.

```text
git status --short

git diff --stat

git diff --check

python3 -m pytest
```

## CI status

### Product CI status

- [ ] Passing:
- [ ] Pending:
- [ ] Failing:
- [ ] Not applicable:

### AgentOps CI status

- [ ] Passing:
- [ ] Pending:
- [ ] Failing:
- [ ] Not applicable:

## Runner / infrastructure caveats

- [ ] None.
- [ ] Self-hosted runner/toolcache/network caveat:

## Suggested verification checklist

- [ ] `make agentops-test`
- [ ] `make agentops-pr`
- [ ] `make hooks-smoke`
- [ ] `make mcp-smoke`
- [ ] `make test`
- [ ] Other repo-specific checks from `docs/verification.md` if applicable.

## Risks / follow-ups

-

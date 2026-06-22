# Chain Implementation Prompt

Work on GitHub issue #<ISSUE_NUMBER> in chain:

```text
<CHAIN>
```

Read:

1. `AGENTS.md`
2. `docs/issue-map.md`
3. `docs/verification.md`
4. `docs/agentops/sequential-chain-workflow.md`
5. `docs/agentops/subagent-playbook.md`
6. the issue body
7. only files needed for this issue

Preflight:

- Run `git status --short`.
- Confirm dependencies, owned files, blocked files, validation, and stop conditions.
- Run `python3 -m tools.agentops.chain_status --chain "<CHAIN>"` with current fixtures or `--github` when live GitHub access is intended.
- Stop if the issue is stale, blocked, already implemented, or needs blocked files.

Implement the smallest safe change for this issue only.

Validation:

- Run focused checks from the issue body.
- Run `git diff --check`.
- Run `python3 -m pytest` and `make agentops-pr` when product/runtime/shared workflow files changed or before PR creation.

PR:

- Use `docs/agentops/templates/pr-body-chain.md`.
- Include `Closes #<ISSUE_NUMBER>`.
- Name stacked base branch or base PR if not targeting `main`.

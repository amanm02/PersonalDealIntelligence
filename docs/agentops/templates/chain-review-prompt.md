# Chain Review Prompt

Review PR #<PR_NUMBER> for issue #<ISSUE_NUMBER> in chain:

```text
<CHAIN>
```

Read:

- `AGENTS.md`
- `docs/verification.md`
- `docs/agentops/sequential-chain-workflow.md`
- linked issue body
- PR diff and PR body

Check:

- dependency and base branch are correct;
- owned files match the issue contract;
- blocked files and product-safety boundaries are untouched;
- tests prove the changed surface;
- PR body includes `Closes #<ISSUE_NUMBER>`, validation, and product safety;
- stacked PR names its base branch or base PR.

Return:

- Blockers
- Non-blocking issues
- Validation gaps
- Closeout risk
- Suggested follow-ups

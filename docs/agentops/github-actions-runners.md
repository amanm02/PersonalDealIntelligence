# GitHub Actions Runners

This repository uses an organization-level self-hosted runner from the `amanm02` organization for AgentOps GitHub Actions.

## Expected workflow selector

```yaml
runs-on: [self-hosted, macOS, ARM64]
```

This syntax is correct for an organization-level self-hosted runner as long as the org runner is made available to `amanm02/PersonalDealIntelligence` and has all three labels.

Do not describe the runner as repository-level unless inspection confirms it is registered directly under this repository's runner settings.

## Setup checklist

- [ ] Confirm the org runner group allows `amanm02/PersonalDealIntelligence`.
- [ ] Confirm the runner is online.
- [ ] Confirm labels include `self-hosted`, `macOS`, and `ARM64`.
- [ ] Confirm the runner process is active before relying on CI.

## Operational notes

- If the runner is offline, asleep, or the runner process is stopped, GitHub Actions jobs may queue.
- Keep runner assumptions documented here and in `docs/verification.md`.
- The AgentOps workflow is scoped to AgentOps checks and does not replace general CI.

## Validation

After setup, run locally:

```bash
make agentops-pr
make hooks-smoke
make mcp-smoke
```

Then confirm the GitHub Actions job is picked up by the organization-level runner.

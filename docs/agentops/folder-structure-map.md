# Folder Structure Map

```text
.
|-- AGENTS.md
|-- MEMORY.md
|-- Makefile
|-- README.md
|-- pyproject.toml
|-- .agents/skills/
|-- .codex/
|   |-- agents/
|   |-- rules/
|   |-- config.toml
|   `-- hooks.json
|-- .github/
|   |-- PULL_REQUEST_TEMPLATE.md
|   `-- workflows/agentops.yml
|-- docs/
|   |-- agentops/
|   |   `-- templates/
|   |-- architecture/
|   |-- implementation-plans/
|   |-- release-checklists/
|   |-- roadmap/
|   |-- specs/
|   |-- decisions.md
|   |-- issue-map.md
|   |-- prompt-library.md
|   `-- verification.md
|-- examples/
|-- src/pdi/
|-- tests/
`-- tools/agentops/
```

## Placement rules

- Stable agent entry map: `AGENTS.md`.
- Durable repo facts: `MEMORY.md`.
- User-facing setup and overview: `README.md`.
- Banking MVP architecture: `docs/architecture/banking-mvp.md`.
- Active issue order: `docs/issue-map.md`.
- Verification source of truth: `docs/verification.md`.
- Detailed AgentOps docs and registries: `docs/agentops/`.
- Reusable AgentOps prompt and report templates: `docs/agentops/templates/`.
- Implementation plans: `docs/implementation-plans/`.
- Project specs: `docs/specs/`.
- Product code: `src/pdi/`.
- Tests: `tests/`.
- Audit scripts: `tools/agentops/`.
- Reusable skills: `.agents/skills/`.
- Codex config, hooks, rules, and subagents: `.codex/`.

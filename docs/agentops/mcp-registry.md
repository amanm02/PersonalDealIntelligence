# MCP Registry

Every MCP entry should document purpose, access, constraints, and smoke tests.

| MCP | Purpose | Read/write | Auth required | Smoke test | Status |
|---|---|---|---|---|---|
| None configured in this repository | No repo-owned MCP server is currently required for Banking MVP or AgentOps checks | none | no | `make mcp-smoke` verifies this registry exists | active |

## Required fields for future entries

For each MCP, document:

- Name
- Purpose
- Read/write classification
- Authentication requirements
- Safe use cases
- Forbidden use cases
- Input and output expectations
- Failure modes
- Smoke test
- Owner
- Retirement criteria

## Default policy

Do not add MCPs because they are available. Add them only when they make the repo workflow safer, faster, or more reliable.

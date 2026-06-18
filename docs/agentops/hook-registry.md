# Hook Registry

Hooks should be deterministic, low-noise, and testable. Current hooks are advisory because the router does not inspect structured tool payloads. Add blocking behavior only when the hook can identify a clear unsafe action deterministically.

| Hook | Event | Purpose | Blocks? | Test command |
|---|---|---|---:|---|
| load-agent-map | SessionStart | Surface key repo guidance | No | `make hooks-smoke` |
| prompt-scope-check | UserPromptSubmit | Warn about ambiguous or risky scope | No | `make hooks-smoke` |
| dangerous-action-guard | PreToolUse | Remind agents to require approval for sensitive files, irreversible actions, credentials, or financial automation | No | `make hooks-smoke` |
| tool-result-audit | PostToolUse | Remind agents to record repeated tool result anomalies | No | `make hooks-smoke` |
| verification-reminder | Stop | Remind agents to report exact verification commands and results | No | `make hooks-smoke` |

## Hook standard

A hook is allowed only if:

- It has one purpose.
- It is deterministic.
- It has an actionable message.
- It is classified as blocking or warning.
- It has a smoke test.
- It does not duplicate CI without a reason.

## Blocking standard

Blocking hooks are allowed only for clear unsafe actions with deterministic detection, such as known secret-file edits, destructive repository commands, or unbounded automation loops. Advisory hooks are preferred when the hook lacks enough structured context to make a safe blocking decision.

# GitHub And Codex Runbook

Use this runbook when an agent needs GitHub metadata, PR publishing, or thread
inspection during Personal Deal Intelligence work.

## GitHub CLI

- Prefer `gh` for issue, PR, and Actions metadata.
- Treat network access errors separately from authentication errors. A sandboxed
  or blocked network call does not prove the token is invalid.
- For read-only GitHub inspection, rerun with the approved network-capable path
  when the environment requires escalation.
- Use supported local `gh` flags. If a prompt references an unsupported flag,
  fall back to `gh pr view --comments` or `--json` fields instead of guessing.
- Do not use live GitHub state to mutate issues, PRs, or labels unless the task
  explicitly asks for that mutation.

## Pull Requests

- Verify open PRs before starting work that could overlap.
- Record linked issue, dependency status, owned files, blocked files,
  validation results, Product CI status, AgentOps CI status, and runner caveats.
- For stacked work, name the base PR or branch and the intended merge order.

## Codex Threads

- Use `list_threads`, when available, to find related project work before
  assuming a failure is new.
- Use minimal `read_thread` arguments first. Add paging cursors only when older
  turns are needed.
- Treat thread previews as hints, not source-of-truth implementation state.
  Verify repo, issue, PR, and CI state before editing.

## Stop Conditions

Stop and report when:

- GitHub state cannot be inspected and the task depends on it.
- A related PR already owns the requested files.
- A branch or worktree has unowned dirty changes.
- A CI failure cannot be classified as product, AgentOps, dependency, runner, or
  unknown from available logs.

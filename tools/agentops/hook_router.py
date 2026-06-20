from __future__ import annotations

import argparse


def session_start() -> int:
    print("AgentOps hook: read AGENTS.md, docs/verification.md, MEMORY.md, and docs/agentops/README.md.")
    return 0


def prompt_scope() -> int:
    print("AgentOps hook: keep work bounded to the Banking MVP issue and use implementation plans for large changes.")
    return 0


def pre_tool() -> int:
    print("AgentOps hook: require explicit approval for sensitive files, irreversible actions, credentials, or financial automation.")
    return 0


def post_tool() -> int:
    print("AgentOps hook: record repeated tool problems in docs/agentops/improvement-backlog.md.")
    return 0


def stop() -> int:
    print("AgentOps hook: include exact validation commands and results before reporting completion.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("event", choices=["session-start", "prompt-scope", "pre-tool", "post-tool", "stop"])
    args = parser.parse_args()
    return {
        "session-start": session_start,
        "prompt-scope": prompt_scope,
        "pre-tool": pre_tool,
        "post-tool": post_tool,
        "stop": stop,
    }[args.event]()


if __name__ == "__main__":
    raise SystemExit(main())

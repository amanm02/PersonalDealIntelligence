# Subagent Playbook

Use subagents to produce narrow findings that help the hub decide faster. Do not use them to duplicate the hub's plan.

## Decision Tree

Use one hub only when:

- the issue touches one file family;
- dependencies and owned files are obvious;
- validation is already named in the issue;
- the change is docs-only or a small test-only patch.
- an agent-limit event has already occurred in the chain.

Use read-only spokes when:

- dependency state could be stale;
- the issue may overlap shared files;
- test scope is unclear;
- a validation failure needs classification;
- the diff is large enough to need an independent scope review.

Avoid spokes when:

- the spoke would read the same docs and restate the issue;
- the chain is blocked on a merge or decision;
- the hub has not extracted a concrete question;
- the task is sequential and the spoke would start implementing future work.

## Useful Spokes

| Spoke | Input | Output |
|---|---|---|
| Dependency audit | Issue, PR list, issue-map row | `ready`, `ready stacked`, or `blocked` with one reason |
| File ownership audit | Issue body and likely touched paths | allowed files, blocked-risk files, narrow route |
| Test plan | Issue body and touched layer | focused tests, full gate, skipped checks with reason |
| Failure triage | failing command and log | failure class, suspected cause, smallest next command |
| Post-diff review | diff and issue contract | blockers, validation gaps, scope creep |

## Spoke Contract

Every spoke prompt should fit in one screen and include:

- the issue or PR number;
- the exact question to answer;
- files or commands it may inspect;
- a statement that it must not edit files;
- a required output format with at most five bullets.

Good output is a verdict with evidence. Bad output is a second implementation plan.

Use `docs/agentops/templates/subagent-readonly-audit.md` for the default spoke prompt.

## Recent Chain Lessons

The #69 through #75 campaign benefited from spokes for issue review, file ownership, validation planning, and post-diff review. It wasted tokens when multiple spokes restated the full issue body, repeated repo rules, or produced overlapping plans for sequential issues that the hub still had to decide.

The first implementation thread spawned 46 subagents and hit agent-limit events. The second thread spawned 26 and had no agent-limit keyword hits in the parsed log. That is the target direction: fewer spokes, narrower questions, faster closeout.

For future chains, run fewer spokes per issue after the first three issues establish the pattern. Keep a single reusable test-plan spoke for similar issues rather than asking every spoke to rediscover the same validation ladder.

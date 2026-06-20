# Harness Scorecard

Score each harness component from 1 to 5. Initial scores are conservative and should be revisited during monthly AgentOps review.

| Component | Score | Questions |
|---|---:|---|
| Instructions | 4 | Are constraints explicit and non-conflicting? |
| Tools | 3 | Are tools narrow and discoverable? |
| MCPs | 3 | Are MCPs necessary and safe? |
| Function calls | 2 | Are schemas strict and testable? |
| Routing | 3 | Does the agent know which workflow to use? |
| Hooks | 3 | Are bad actions caught early? |
| Tests | 4 | Can work be verified without guessing? |
| Evals | 1 | Can before/after behavior be compared? |
| Observability | 2 | Can defects be reconstructed? |
| Docs | 4 | Can a fresh agent understand the repo? |

## Scoring notes

- 1: absent or actively harmful
- 2: present but incomplete
- 3: usable but inconsistent
- 4: reliable and mostly complete
- 5: clear, tested, and maintained

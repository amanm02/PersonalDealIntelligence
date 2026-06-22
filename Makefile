.PHONY: agentops-pr workflow-hygiene agentops-weekly agentops-monthly hooks-smoke mcp-smoke test agentops-test agentops-chain-status agentops-issue-contracts agentops-context-budget agentops-pr-body

test:
	python3 -m pytest

workflow-hygiene:
	python3 -m tools.agentops.check_pr_template
	python3 -m tools.agentops.check_prompt_library
	python3 -m tools.agentops.check_issue_hygiene
	python3 -m tools.agentops.check_issue_map_freshness
	python3 -m tools.agentops.check_work_state --advisory
	python3 -m tools.agentops.worktree_report
	python3 -m tools.agentops.check_generated_artifacts
	python3 -m tools.agentops.recommend_next_issue
	python3 -m tools.agentops.check_context_budget
	python3 -m tools.agentops.check_pr_body --body-file docs/agentops/templates/pr-body-chain.md --chain --require-closure

agentops-pr: workflow-hygiene
	python3 -m tools.agentops.audit_docs
	python3 -m tools.agentops.audit_memory
	python3 -m tools.agentops.audit_structure
	python3 -m tools.agentops.audit_tools
	python3 -m tools.agentops.audit_hooks

agentops-weekly:
	python3 -m tools.agentops.find_stale_docs
	python3 -m tools.agentops.check_context_budget
	python3 -m tools.agentops.score_harness

agentops-monthly:
	python3 -m tools.agentops.generate_improvement_backlog
	python3 -m tools.agentops.audit_mcp
	python3 -m tools.agentops.audit_function_schemas

hooks-smoke:
	python3 -m tools.agentops.audit_hooks --smoke

mcp-smoke:
	python3 -m tools.agentops.audit_mcp --smoke

agentops-test: agentops-pr hooks-smoke mcp-smoke
	python3 -m pytest tests/agentops -q

agentops-chain-status:
	python3 -m tools.agentops.chain_status --chain "$${CHAIN:-69,72,78,81,68,71,77,80,70,73,79,82,83,34,74,75}" $${ISSUES_JSON:+--issues-json "$${ISSUES_JSON}"} $${PRS_JSON:+--prs-json "$${PRS_JSON}"}

agentops-issue-contracts:
	python3 -m tools.agentops.check_issue_hygiene

agentops-context-budget:
	python3 -m tools.agentops.check_context_budget

agentops-pr-body:
	python3 -m tools.agentops.check_pr_body --body-file "$${BODY_FILE:-docs/agentops/templates/pr-body-chain.md}" --chain --require-closure

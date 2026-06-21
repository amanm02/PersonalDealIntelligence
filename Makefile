.PHONY: agentops-pr workflow-hygiene agentops-weekly agentops-monthly hooks-smoke mcp-smoke test agentops-test

test:
	python3 -m pytest

workflow-hygiene:
	python3 tools/agentops/check_pr_template.py
	python3 tools/agentops/check_issue_map_freshness.py
	python3 tools/agentops/check_context_budget.py

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

agentops-test: agentops-pr hooks-smoke mcp-smoke test

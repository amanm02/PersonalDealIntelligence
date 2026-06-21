from tools.agentops import summarize_ci_failure


def test_classifies_product_test_failure() -> None:
    text = """
    __________________ test_policy_rejects_private_session __________________
    FAILED tests/sources/test_policy.py::test_policy_rejects_private_session
    src/pdi/sources/policy.py:42: AssertionError
    """

    summary = summarize_ci_failure.classify_ci_failure(text)

    assert summary.category == summarize_ci_failure.PRODUCT_TEST_FAILURE
    assert "FAILED tests/sources/test_policy.py" in summary.markers[0]


def test_classifies_agentops_failure() -> None:
    text = """
    python3 -m tools.agentops.audit_tools
    FAIL missing docs/agentops/tool-registry.md
    audit_registries: FAIL
    """

    summary = summarize_ci_failure.classify_ci_failure(text)

    assert summary.category == summarize_ci_failure.AGENTOPS_FAILURE
    assert summary.markers


def test_classifies_runner_setup_failure() -> None:
    text = """
    Error: Version 3.12 was not found in the local cache
    Hosted tool cache lookup failed during setup-python
    """

    summary = summarize_ci_failure.classify_ci_failure(text)

    assert summary.category == summarize_ci_failure.RUNNER_SETUP_FAILURE


def test_classifies_dependency_install_failure() -> None:
    text = """
    ERROR: Could not find a version that satisfies the requirement impossible-pkg
    ERROR: No matching distribution found for impossible-pkg
    """

    summary = summarize_ci_failure.classify_ci_failure(text)

    assert summary.category == summarize_ci_failure.DEPENDENCY_INSTALL_FAILURE


def test_classifies_unknown_when_no_marker_matches() -> None:
    summary = summarize_ci_failure.classify_ci_failure("job stopped unexpectedly")

    assert summary.category == summarize_ci_failure.UNKNOWN
    assert summary.markers == ()


def test_reads_fixture_file_inputs(tmp_path) -> None:
    fixture = tmp_path / "agentops.log"
    fixture.write_text(
        "FAILED tests/agentops/test_worktree_report.py::test_report\n",
        encoding="utf-8",
    )

    text = summarize_ci_failure.read_input([str(fixture)])
    summary = summarize_ci_failure.classify_ci_failure(text)

    assert "tests/agentops/test_worktree_report.py" in text
    assert summary.category == summarize_ci_failure.AGENTOPS_FAILURE


def test_reads_inline_log_text() -> None:
    text = summarize_ci_failure.read_input(["npm ERR! failed to resolve package"])
    summary = summarize_ci_failure.classify_ci_failure(text)

    assert summary.category == summarize_ci_failure.DEPENDENCY_INSTALL_FAILURE

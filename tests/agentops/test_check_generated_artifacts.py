from tools.agentops import check_generated_artifacts


def test_generated_artifact_detection_flags_python_caches() -> None:
    lines = [
        " M src/pdi/cli.py",
        "?? src/pdi/__pycache__/cli.cpython-313.pyc",
        "?? .pytest_cache/v/cache/nodeids",
    ]

    offenders = check_generated_artifacts.find_generated_status_entries(lines)

    assert offenders == [
        "?? src/pdi/__pycache__/cli.cpython-313.pyc",
        "?? .pytest_cache/v/cache/nodeids",
    ]


def test_generated_artifact_detection_ignores_normal_files() -> None:
    lines = [
        " M docs/verification.md",
        "?? tests/agentops/test_check_generated_artifacts.py",
    ]

    assert check_generated_artifacts.find_generated_status_entries(lines) == []


def test_generated_artifact_detection_flags_tracked_cache_paths() -> None:
    paths = [
        "src/pdi/cli.py",
        "tests/__pycache__/test_cli.cpython-313.pyc",
        ".pytest_cache/v/cache/nodeids",
    ]

    assert check_generated_artifacts.find_generated_tracked_files(paths) == [
        "tests/__pycache__/test_cli.cpython-313.pyc",
        ".pytest_cache/v/cache/nodeids",
    ]


def test_status_path_handles_renames() -> None:
    assert (
        check_generated_artifacts.status_path("R  old.py -> src/pdi/new.py")
        == "src/pdi/new.py"
    )

# mypy: ignore-errors
# tests/unit/conftest.py

# tests/unit/conftest.py
"""
CRITICAL: This file MUST be named conftest.py and placed in tests/unit/
It runs BEFORE any test files are imported, preventing real directory creation.
"""

import os

# import sys
import tempfile
from pathlib import Path
import pytest

# =====================================================================
# STEP 1: SET ENV VARS BEFORE ANY TREEHOPPER IMPORTS
# =====================================================================

# Create a session-level temp directory for ALL unit tests
_UNIT_TEST_ROOT = None


def _setup_test_env():
    """
    Called once at import time to set up test environment.
    This prevents ANY treehopper module from creating real directories.
    """
    global _UNIT_TEST_ROOT

    if _UNIT_TEST_ROOT is None:
        # Create temp directory that persists for entire test session
        _UNIT_TEST_ROOT = tempfile.mkdtemp(prefix="treehopper-unit-tests-")
        print(f"\n🧪 Unit tests using temp root: {_UNIT_TEST_ROOT}")

    # Set environment variables BEFORE any imports
    os.environ["TH_ROOT"] = _UNIT_TEST_ROOT
    os.environ["TREEHOPPER_RUNTIME_DIR"] = os.path.join(_UNIT_TEST_ROOT, "runtime")
    os.environ["TREEHOPPER_CANCEL_DIR"] = os.path.join(
        _UNIT_TEST_ROOT, "runtime", "cancels"
    )
    os.environ["TH_TEST_MODE"] = "1"

    # Prevent real directory creation
    os.environ["TREEHOPPER_NO_AUTO_DIRS"] = "1"  # If your code checks this

    return _UNIT_TEST_ROOT


# Call immediately at module import time
_UNIT_TEST_ROOT = _setup_test_env()


# =====================================================================
# STEP 2: SESSION-LEVEL FIXTURE FOR PATH VERIFICATION
# =====================================================================


@pytest.fixture(scope="session", autouse=True)
def verify_no_home_pollution():
    """
    Verify that unit tests never touch ~/.treehopper
    """
    real_home = Path.home() / ".treehopper"

    # Snapshot BEFORE tests
    before_exists = real_home.exists()
    before_files = set()
    if before_exists:
        before_files = {str(p.relative_to(real_home)) for p in real_home.rglob("*")}

    print(
        f"\n📸 Before tests: ~/.treehopper exists={before_exists}, files={len(before_files)}"
    )

    yield

    # Check AFTER tests
    after_exists = real_home.exists()
    after_files = set()
    if after_exists:
        after_files = {str(p.relative_to(real_home)) for p in real_home.rglob("*")}

    print(
        f"\n📸 After tests: ~/.treehopper exists={after_exists}, files={len(after_files)}"
    )

    # Detect pollution
    if not before_exists and after_exists:
        pytest.fail(
            f"❌ Unit tests CREATED ~/.treehopper directory!\nContents: {sorted(after_files)}"
        )

    if before_exists and after_exists:
        new_files = after_files - before_files
        if new_files:
            pytest.fail(
                f"❌ Unit tests created {len(new_files)} new files in ~/.treehopper:\n{sorted(new_files)}"
            )

    print("✅ Unit tests did NOT pollute ~/.treehopper")


# =====================================================================
# STEP 3: FUNCTION-LEVEL FIXTURE FOR PATH ISOLATION
# =====================================================================


@pytest.fixture(autouse=True)
def isolate_paths(tmp_path, monkeypatch):
    """
    Per-test isolation: ensures each test uses its own temp directory.
    This runs AFTER imports, so it catches any runtime directory creation.
    """
    # Import here (after env vars are set)
    import treehopper.th_config as th_config

    # Create test-specific temp structure
    test_reg = tmp_path / "registry"
    test_agents = test_reg / "agents"
    test_chains = test_reg / "chains"
    test_runtime = tmp_path / "runtime"
    test_cancel = test_runtime / "cancels"
    test_archive = tmp_path / "archive"

    for d in [
        test_reg,
        test_agents,
        test_chains,
        test_runtime,
        test_cancel,
        test_archive,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # Patch th_config
    path_overrides = {
        "TH_ROOT": tmp_path,
        "REGISTRY_DIR": test_reg,
        "REGISTRY_AGENTS": test_agents,
        "REGISTRY_AGENTS_INDEX": test_agents / "agents.json",
        "CHAINS_DIR": test_chains,
        "CHAINS_INDEX": test_chains / "chains.json",
        "RUNTIME_DIR": test_runtime,
        "CANCEL_DIR": test_cancel,
        "ARCHIVE_DIR": test_archive,
    }

    for constant, value in path_overrides.items():
        monkeypatch.setattr(th_config, constant, value)

    # Patch all modules that import these constants
    modules_to_patch = [
        "treehopper.treehopper",
        "treehopper.treehopper_cli",
        "treehopper.treehopper_chains",
        "treehopper.utils.run_registry",
        "treehopper.utils.commons",
        "treehopper.chains_agents_refresh_status",
        "treehopper.websockets.ws_manager",
    ]

    for module_name in modules_to_patch:
        for constant, value in path_overrides.items():
            monkeypatch.setattr(f"{module_name}.{constant}", value, raising=False)

    # Also patch environment variables for any subprocess calls
    monkeypatch.setenv("TH_ROOT", str(tmp_path))
    monkeypatch.setenv("TREEHOPPER_RUNTIME_DIR", str(test_runtime))
    monkeypatch.setenv("TREEHOPPER_CANCEL_DIR", str(test_cancel))

    yield tmp_path


# =====================================================================
# STEP 4: CLEANUP AFTER SESSION
# =====================================================================


@pytest.fixture(scope="session", autouse=True)
def cleanup_temp_root():
    """
    Clean up the session-level temp directory after all tests complete.
    """
    yield

    if _UNIT_TEST_ROOT and Path(_UNIT_TEST_ROOT).exists():
        import shutil

        try:
            shutil.rmtree(_UNIT_TEST_ROOT)
            print(f"\n🧹 Cleaned up temp test root: {_UNIT_TEST_ROOT}")
        except Exception as e:
            print(f"\n⚠️  Could not clean up {_UNIT_TEST_ROOT}: {e}")


# =====================================================================
# STEP 5: VERIFY IMPORTS USE TEMP PATHS
# =====================================================================


def pytest_configure(config):
    """
    Hook called after command line options are parsed.
    Verifies that th_config is using test paths.
    """
    # Import after env vars are set
    try:
        import treehopper.th_config as th_config

        actual_root = str(th_config.TH_ROOT)
        expected_root = _UNIT_TEST_ROOT

        if str(Path.home()) in actual_root:
            print("\n❌ WARNING: th_config.TH_ROOT points to home directory!")
            print(f"   TH_ROOT = {actual_root}")
            print(f"   Expected = {expected_root}")
        else:
            print(f"\n✅ th_config using test paths: {actual_root}")
    except ImportError:
        pass  # Module not available yet


# =====================================================================
# VERIFICATION TEST (Add to any test file to double-check)
# =====================================================================


def test_conftest_isolation_works(tmp_path):
    """
    Verification test: ensures conftest.py isolation is working.
    This test should always pass if conftest.py is properly configured.
    """
    import treehopper.th_config as th_config
    from pathlib import Path

    # Verify we're not using home directory
    assert str(Path.home()) not in str(
        th_config.TH_ROOT
    ), f"th_config.TH_ROOT is using home directory: {th_config.TH_ROOT}"

    # Verify we're using a temp directory
    assert str(tmp_path) in str(th_config.TH_ROOT) or "/tmp/" in str(
        th_config.TH_ROOT
    ), f"th_config.TH_ROOT is not in a temp directory: {th_config.TH_ROOT}"

    # Verify specific paths
    assert str(Path.home()) not in str(th_config.REGISTRY_DIR)
    assert str(Path.home()) not in str(th_config.CHAINS_DIR)
    assert str(Path.home()) not in str(th_config.RUNTIME_DIR)

    print(f"✅ Isolation verified! Using: {th_config.TH_ROOT}")

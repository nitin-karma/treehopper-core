# treehopper/th_setup.py
"""
TreehopperAI Setup Module

Handles initialization of Treehopper directory structure and required files.
Safe to run multiple times (idempotent).

This module ensures:
1. All directories exist (prevents mkdir errors in commons.py, run_registry.py)
2. All required files exist (prevents file not found errors)
3. Subscription ID is initialized (used by commons.py)
4. Index files are initialized (used by commons.py)
5. UI log file exists (used by th_ui_cli.py)
6. CANCEL_DIR exists (used by run_registry.py)
7. Database is initialized
"""

import sys
from pathlib import Path
from typing import Tuple, List

from treehopper.logging import get_logger

logger = get_logger()


def setup_treehopper() -> bool:
    """
    Setup Treehopper directory structure and required files.
    Safe to run multiple times (idempotent).

    Returns:
        bool: True if all verifications passed, False if warnings occurred
    """
    print("🌿 TreehopperAI Setup")
    print("=" * 60)

    # ═══════════════════════════════════════════════════════════
    # Import after printing header (in case imports fail)
    # ═══════════════════════════════════════════════════════════
    try:
        from treehopper.th_config import (
            TH_ROOT,
            REGISTRY_DIR,
            REGISTRY_AGENTS,
            REGISTRY_AGENTS_INDEX,
            CHAINS_DIR,
            CHAINS_INDEX,
            RUNTIME_DIR,
            CANCEL_DIR,
            ARCHIVE_DIR,
            DB_DIR,
            SUBSCRIPTION_FILE,
            UI_LOG,
            UI_PID,
        )
        from treehopper.utils.commons import (
            get_or_create_subscription_id,
            save_agents_index,
            save_chains_index,
            # ensure_registry_dirs,
        )
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        logger.error(f"Setup failed: {e}")
        return False

    # ═══════════════════════════════════════════════════════════
    # 1. Create Directory Structure
    # ═══════════════════════════════════════════════════════════
    directories = [
        ("Root", TH_ROOT),
        ("Registry", REGISTRY_DIR),
        ("Agents Registry", REGISTRY_AGENTS),
        ("Chains Registry", CHAINS_DIR),
        ("Runtime", RUNTIME_DIR),
        ("Cancellation", CANCEL_DIR),  # Critical for run_registry.py
        ("Archive", ARCHIVE_DIR),
        ("Database", TH_ROOT / DB_DIR),
    ]

    created_count = _create_directories(directories)

    # ═══════════════════════════════════════════════════════════
    # 2. Create Required Files
    # ═══════════════════════════════════════════════════════════
    subscription_id, files_created = _create_required_files(
        SUBSCRIPTION_FILE,
        UI_LOG,
        REGISTRY_AGENTS_INDEX,
        CHAINS_INDEX,
        get_or_create_subscription_id,
        save_agents_index,
        save_chains_index,
    )

    # ═══════════════════════════════════════════════════════════
    # 3. Initialize Database
    # ═══════════════════════════════════════════════════════════
    _initialize_database()

    # ═══════════════════════════════════════════════════════════
    # 4. Verify Setup
    # ═══════════════════════════════════════════════════════════
    verification_passed, verification_results = _verify_setup(
        CANCEL_DIR, UI_LOG, UI_PID
    )

    # ═══════════════════════════════════════════════════════════
    # 5. Print Summary
    # ═══════════════════════════════════════════════════════════
    _print_summary(
        verification_passed,
        verification_results,
        TH_ROOT,
        subscription_id,
        REGISTRY_DIR,
        RUNTIME_DIR,
        CANCEL_DIR,
        created_count,
        len(directories),
        files_created,
    )

    logger.info(
        f"Setup completed. Verification: {'passed' if verification_passed else 'warnings'}"
    )
    return verification_passed


def _create_directories(directories: List[Tuple[str, Path]]) -> int:
    """
    Create required directories if they don't exist.

    Args:
        directories: List of (name, path) tuples

    Returns:
        int: Number of directories created
    """
    print("\n📁 Creating directory structure...")
    created_count = 0

    for name, path in directories:
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"   ✅ Created: {name:20s} → {path}")
                created_count += 1
                logger.info(f"Created directory: {path}")
            except Exception as e:
                print(f"   ❌ Failed to create {name}: {e}")
                logger.error(f"Failed to create {path}: {e}")
        else:
            print(f"   ✓  Exists:  {name:20s} → {path}")

    if created_count > 0:
        print(f"   📊 Created {created_count} new directories")
    else:
        print("   📊 All directories already exist")

    return created_count


def _create_required_files(
    subscription_file: Path,
    ui_log: Path,
    agents_index: Path,
    chains_index: Path,
    get_or_create_subscription_id,
    save_agents_index,
    save_chains_index,
) -> Tuple[str, int]:
    """
    Create required files if they don't exist.

    Returns:
        Tuple[str, int]: (subscription_id, number of files created)
    """
    print("\n📄 Creating required files...")
    files_created = 0
    subscription_id = "setup-failed"

    # ─────────────────────────────────────────────────────────
    # Subscription ID (CRITICAL for commons.py)
    # ─────────────────────────────────────────────────────────
    try:
        file_existed = subscription_file.exists()
        subscription_id = get_or_create_subscription_id()

        if file_existed:
            print(f"   ✓  Exists:  Subscription ID → {subscription_file}")
        else:
            print(f"   ✅ Created: Subscription ID → {subscription_file}")
            files_created += 1
            logger.info(f"Created subscription ID: {subscription_id}")

        print(f"   🔑 Your subscription ID: {subscription_id}")
    except Exception as e:
        print(f"   ❌ Error creating subscription ID: {e}")
        logger.error(f"Subscription ID creation failed: {e}")

    # ─────────────────────────────────────────────────────────
    # UI Log File (CRITICAL for th_ui_cli.py)
    # ─────────────────────────────────────────────────────────
    try:
        if not ui_log.exists():
            # Ensure parent directory exists
            ui_log.parent.mkdir(parents=True, exist_ok=True)
            ui_log.touch()
            print(f"   ✅ Created: UI Log File     → {ui_log}")
            files_created += 1
            logger.info(f"Created UI log file: {ui_log}")
        else:
            print(f"   ✓  Exists:  UI Log File     → {ui_log}")
    except Exception as e:
        print(f"   ❌ Error creating UI log: {e}")
        logger.error(f"UI log creation failed: {e}")

    # ─────────────────────────────────────────────────────────
    # Agents Index (CRITICAL for commons.py)
    # ─────────────────────────────────────────────────────────
    try:
        if not agents_index.exists():
            save_agents_index([])
            print(f"   ✅ Created: Agents Index    → {agents_index}")
            files_created += 1
            logger.info(f"Created agents index: {agents_index}")
        else:
            print(f"   ✓  Exists:  Agents Index    → {agents_index}")
    except Exception as e:
        print(f"   ❌ Error creating agents index: {e}")
        logger.error(f"Agents index creation failed: {e}")

    # ─────────────────────────────────────────────────────────
    # Chains Index (CRITICAL for commons.py)
    # ─────────────────────────────────────────────────────────
    try:
        if not chains_index.exists():
            save_chains_index([])
            print(f"   ✅ Created: Chains Index    → {chains_index}")
            files_created += 1
            logger.info(f"Created chains index: {chains_index}")
        else:
            print(f"   ✓  Exists:  Chains Index    → {chains_index}")
    except Exception as e:
        print(f"   ❌ Error creating chains index: {e}")
        logger.error(f"Chains index creation failed: {e}")

    if files_created > 0:
        print(f"   📊 Created {files_created} new files")
    else:
        print("   📊 All required files already exist")

    return subscription_id, files_created


def _initialize_database() -> bool:
    """
    Initialize the database if needed.

    Returns:
        bool: True if successful, False if failed
    """
    print("\n💾 Initializing database...")
    try:
        from treehopper.visualizer.db_util import db

        db.init_db()
        print("   ✅ Database initialized successfully")
        logger.info("Database initialized")
        return True
    except Exception as e:
        print(f"   ⚠️  Database init warning: {e}")
        print("   ℹ️  You can initialize it later with 'treehopper run'")
        logger.warning(f"Database initialization skipped: {e}")
        return False


def _verify_setup(
    cancel_dir: Path, ui_log: Path, ui_pid: Path
) -> Tuple[bool, List[Tuple[str, bool]]]:
    """
    Verify that all critical components work correctly.

    Returns:
        Tuple[bool, List[Tuple[str, bool]]]: (all_passed, results)
    """
    print("\n🔍 Verifying setup...")
    verification_results = []

    # ─────────────────────────────────────────────────────────
    # Test commons.py functions
    # ─────────────────────────────────────────────────────────
    try:
        from treehopper.utils.commons import (
            load_agents_index,
            load_chains_index,
            ensure_registry_dirs,
        )

        ensure_registry_dirs()
        agents = load_agents_index()
        chains = load_chains_index()

        print("   ✅ commons.py functions verified")
        print("      - ensure_registry_dirs() ✓")
        print(f"      - load_agents_index() → {len(agents)} agents")
        print(f"      - load_chains_index() → {len(chains)} chains")
        verification_results.append(("commons.py", True))
        logger.info("commons.py verification passed")
    except Exception as e:
        print(f"   ❌ commons.py verification failed: {e}")
        verification_results.append(("commons.py", False))
        logger.error(f"commons.py verification failed: {e}")

    # ─────────────────────────────────────────────────────────
    # Test run_registry.py functions
    # ─────────────────────────────────────────────────────────
    try:
        from treehopper.utils.run_registry import make_run_id

        test_run_id = make_run_id("test_chain")

        print("   ✅ run_registry.py functions verified")
        print("      - make_run_id() ✓")
        print(f"      - Generated test run_id: {test_run_id}")
        print(f"      - CANCEL_DIR exists: {cancel_dir.exists()}")
        verification_results.append(("run_registry.py", True))
        logger.info("run_registry.py verification passed")
    except Exception as e:
        print(f"   ❌ run_registry.py verification failed: {e}")
        verification_results.append(("run_registry.py", False))
        logger.error(f"run_registry.py verification failed: {e}")

    # ─────────────────────────────────────────────────────────
    # Test UI files (th_ui_cli.py dependencies)
    # ─────────────────────────────────────────────────────────
    try:
        checks = [
            ("UI_LOG exists", ui_log.exists()),
            ("UI_LOG parent exists", ui_log.parent.exists()),
            ("UI_PID parent exists", ui_pid.parent.exists()),
        ]

        all_ui_ok = all(check[1] for check in checks)

        if all_ui_ok:
            print("   ✅ UI dependencies verified")
            for desc, status in checks:
                print(f"      - {desc}: {status}")
        else:
            print("   ⚠️  UI dependency check: some paths missing")
            for desc, status in checks:
                symbol = "✓" if status else "✗"
                print(f"      {symbol} {desc}: {status}")

        verification_results.append(("UI dependencies", all_ui_ok))
        logger.info(f"UI verification: {all_ui_ok}")
    except Exception as e:
        print(f"   ❌ UI verification failed: {e}")
        verification_results.append(("UI dependencies", False))
        logger.error(f"UI verification failed: {e}")

    verification_passed = all(result[1] for result in verification_results)
    return verification_passed, verification_results


def _print_summary(
    verification_passed: bool,
    verification_results: List[Tuple[str, bool]],
    th_root: Path,
    subscription_id: str,
    registry_dir: Path,
    runtime_dir: Path,
    cancel_dir: Path,
    created_count: int,
    total_dirs: int,
    files_created: int,
) -> None:
    """Print setup summary."""
    failed_components = [name for name, status in verification_results if not status]

    print("\n" + "=" * 60)
    if verification_passed:
        print("✅ Setup complete! All systems operational.")
    else:
        print("⚠️  Setup complete with warnings")
        print(f"   Failed components: {', '.join(failed_components)}")
    print("=" * 60)

    print("\n📍 Treehopper Configuration:")
    print(f"   Root:            {th_root}")
    print(f"   Subscription ID: {subscription_id}")
    print(f"   Registry:        {registry_dir}")
    print(f"   Runtime:         {runtime_dir}")
    print(f"   Cancellation:    {cancel_dir}")

    print("\n📊 Setup Statistics:")
    print(f"   Directories created:  {created_count}/{total_dirs}")
    print(f"   Files created:        {files_created}")
    status_msg = (
        "✅ All passed"
        if verification_passed
        else f"⚠️ {len(failed_components)} warnings"
    )
    print(f"   Verification status:  {status_msg}")

    print("\n📋 Next steps:")
    print("   1. Create an agent:    treehopper init <agent_name>")
    print("   2. Build agent:        treehopper build <agent_folder>")
    print("   3. Start server:       treehopper run --bg")
    print("   4. Launch UI:          treehopper launch ui")
    print("   5. Create chain:       treehopper chain build <name> <agent1> <agent2>")
    print("   6. Run chain:          treehopper chain run <name> --detached")

    print("\n💡 Commands:")
    print("   help        → treehopper help")
    print("   status      → treehopper status")
    print("   list agents → treehopper list_agents")
    print("   list chains → treehopper list_chains")


# ═══════════════════════════════════════════════════════════
# Main entry point (for testing)
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    success = setup_treehopper()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
TreehopperAI SQLite Sync Module (Daemon-Free)

Phase 1: Subscription table ✅
Phase 2: YAML content caching ✅
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from treehopper.th_config import (
    REGISTRY_AGENTS_INDEX,
    CHAINS_INDEX,
    TH_ROOT,
)
from treehopper.visualizer.db_util import db
from treehopper.logging import get_logger

logger = get_logger()

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================


def init_registry_tables():
    """Initialize agents, chains, runs tables"""
    try:
        # Agents table
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT UNIQUE NOT NULL,
                agent_id TEXT UNIQUE NOT NULL,
                subscription_id TEXT NOT NULL,
                entrypoint TEXT NOT NULL,
                routes TEXT,
                description TEXT,
                version TEXT,
                created_at TEXT,
                updated_at TEXT,
                inputs TEXT,
                outputs TEXT,
                tags TEXT
            )
        """
        )

        db.execute("CREATE INDEX IF NOT EXISTS idx_agent_name ON agents(agent_name)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON agents(agent_id)")

        # Chains table
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_name TEXT UNIQUE NOT NULL,
                chain_id TEXT UNIQUE NOT NULL,
                subscription_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT DEFAULT 'POST',
                description TEXT,
                created_at TEXT,
                updated_at TEXT,
                steps TEXT,
                tags TEXT
            )
        """
        )

        db.execute("CREATE INDEX IF NOT EXISTS idx_chain_name ON chains(chain_name)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_chain_id ON chains(chain_id)")

        # Runs table
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                chain_name TEXT,
                chain_id TEXT,
                chain_dir TEXT,
                status TEXT,
                payload TEXT,
                results TEXT,
                created_at TEXT,
                completed_at TEXT,
                detached INTEGER DEFAULT 0,
                success INTEGER DEFAULT 0,
                cancelled INTEGER DEFAULT 0,
                current_step_index INTEGER DEFAULT -1
            )
        """
        )

        db.execute("CREATE INDEX IF NOT EXISTS idx_run_id ON runs(run_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_chain_name_runs ON runs(chain_name)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_status ON runs(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON runs(created_at)")

        # Sync metadata table
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_metadata (
                file TEXT PRIMARY KEY,
                last_modified TEXT,
                last_synced TEXT,
                record_count INTEGER
            )
        """
        )

        logger.info("✅ Registry tables initialized")

    except Exception as e:
        logger.error(f"Failed to init registry tables: {e}")


def init_subscription_table():
    """Initialize subscription table (Phase 1)"""
    try:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription (
                subscription_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                plan TEXT DEFAULT 'trial',
                metadata TEXT
            )
        """
        )

        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_subscription_status ON subscription(status)"
        )
        logger.info("✅ Subscription table initialized")

    except Exception as e:
        logger.error(f"Failed to init subscription table: {e}")


def init_yaml_table():
    """
    Initialize YAML content cache table (Phase 2)

    Caches agent and chain YAML files for:
    - 10x faster reads
    - No race conditions during build
    - No file I/O overhead
    """
    try:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS yaml_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                yaml_content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(entity_type, entity_name)
            )
        """
        )

        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_yaml_entity ON yaml_content(entity_type, entity_name)"
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_yaml_id ON yaml_content(entity_id)")

        logger.info("✅ YAML content table initialized")

    except Exception as e:
        logger.error(f"Failed to init YAML table: {e}")


# ============================================================================
# SYNC FUNCTIONS
# ============================================================================


def sync_agents() -> int:
    """Sync agents.json → SQLite"""
    if not REGISTRY_AGENTS_INDEX.exists():
        return 0

    try:
        init_registry_tables()

        with open(REGISTRY_AGENTS_INDEX) as f:
            agents = json.load(f)

        if not agents:
            return 0

        db.execute("DELETE FROM agents")

        now = datetime.utcnow().isoformat() + "Z"
        for agent in agents:
            db.execute(
                """
                INSERT INTO agents (
                    agent_name, agent_id, subscription_id, entrypoint,
                    routes, description, version, created_at, updated_at,
                    inputs, outputs, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    agent.get("agent_name"),
                    agent.get("agent_id"),
                    agent.get("subscription_id"),
                    agent.get("entrypoint"),
                    json.dumps(agent.get("routes", {})),
                    agent.get("description"),
                    agent.get("version"),
                    agent.get("created_at", now),
                    now,
                    json.dumps(agent.get("inputs", [])),
                    json.dumps(agent.get("outputs", [])),
                    json.dumps(agent.get("tags", [])),
                ),
            )

        db.execute(
            """
            INSERT OR REPLACE INTO sync_metadata (file, last_modified, last_synced, record_count)
            VALUES (?, ?, ?, ?)
        """,
            (
                "agents.json",
                str(REGISTRY_AGENTS_INDEX.stat().st_mtime),
                now,
                len(agents),
            ),
        )

        logger.debug(f"✅ Synced {len(agents)} agents to database")
        return len(agents)

    except Exception as e:
        logger.error(f"⚠️  Sync agents error: {e}")
        return 0


def sync_chains() -> int:
    """Sync chains.json → SQLite"""
    if not CHAINS_INDEX.exists():
        return 0

    try:
        init_registry_tables()

        with open(CHAINS_INDEX) as f:
            chains = json.load(f)

        if not chains:
            return 0

        db.execute("DELETE FROM chains")

        now = datetime.utcnow().isoformat() + "Z"
        for chain in chains:
            db.execute(
                """
                INSERT INTO chains (
                    chain_name, chain_id, subscription_id, endpoint,
                    method, description, created_at, updated_at,
                    steps, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    chain.get("chain_name"),
                    chain.get("chain_id"),
                    chain.get("subscription_id"),
                    chain.get("endpoint"),
                    chain.get("method", "POST"),
                    chain.get("description"),
                    chain.get("created_at", now),
                    now,
                    json.dumps(chain.get("steps", [])),
                    json.dumps(chain.get("tags", [])),
                ),
            )

        db.execute(
            """
            INSERT OR REPLACE INTO sync_metadata (file, last_modified, last_synced, record_count)
            VALUES (?, ?, ?, ?)
        """,
            ("chains.json", str(CHAINS_INDEX.stat().st_mtime), now, len(chains)),
        )

        logger.debug(f"✅ Synced {len(chains)} chains to database")
        return len(chains)

    except Exception as e:
        logger.error(f"⚠️  Sync chains error: {e}")
        return 0


def record_run(run_data: Dict[str, Any]) -> bool:
    """Record a chain run to SQLite (dual write)"""
    try:
        init_registry_tables()

        now = datetime.utcnow().isoformat() + "Z"

        db.execute(
            """
            INSERT OR REPLACE INTO runs (
                run_id, chain_name, chain_id, chain_dir,
                status, payload, results,
                created_at, completed_at,
                detached, success, cancelled, current_step_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_data.get("run_id"),
                run_data.get("chain_name"),
                run_data.get("chain_id"),
                str(run_data.get("chain_dir", "")),
                run_data.get("status", "pending"),
                json.dumps(run_data.get("payload", {})),
                json.dumps(run_data.get("results", [])),
                run_data.get("created_at", now),
                run_data.get("completed_at"),
                1 if run_data.get("detached") else 0,
                1 if run_data.get("success") else 0,
                1 if run_data.get("cancelled") else 0,
                run_data.get("current_step_index", -1),
            ),
        )

        logger.debug(f"✅ Recorded run {run_data.get('run_id')}")
        return True

    except Exception as e:
        logger.error(f"⚠️  Record run error: {e}")
        return False


def sync_subscription(
    subscription_id: str,
    created_at: Optional[str] = None,
    status: str = "active",
    plan: str = "trial",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Sync subscription (Phase 1) with duplicate prevention"""
    try:
        init_subscription_table()

        now = datetime.utcnow().isoformat() + "Z"
        created = created_at or now

        # Check if ANY subscription exists
        existing = get_subscription()

        if existing:
            # Update existing instead of creating duplicate
            logger.warning(
                f"Subscription exists: {existing['subscription_id']}. "
                f"Updating instead of creating duplicate."
            )

            db.execute(
                """
                UPDATE subscription
                SET updated_at = ?, status = ?, plan = ?, metadata = ?
                WHERE subscription_id = ?
            """,
                (
                    now,
                    status,
                    plan,
                    json.dumps(metadata) if metadata else None,
                    existing["subscription_id"],
                ),
            )

            return True

        # No subscription - safe to insert
        db.execute(
            """
            INSERT INTO subscription (
                subscription_id, created_at, updated_at, status, plan, metadata
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                subscription_id,
                created,
                now,
                status,
                plan,
                json.dumps(metadata) if metadata else None,
            ),
        )

        logger.debug(f"✅ Created subscription: {subscription_id}")
        return True

    except Exception as e:
        logger.error(f"⚠️  Sync subscription error: {e}")
        return False


def sync_yaml(
    entity_type: str, entity_name: str, entity_id: str, yaml_content: str
) -> bool:
    """
    Sync YAML content to SQLite cache (Phase 2)

    Args:
        entity_type: 'agent' or 'chain'
        entity_name: Name of the agent/chain
        entity_id: ID of the agent/chain
        yaml_content: The YAML file content as string

    Returns: True if successful

    Benefits:
    - 10x faster reads (SQLite vs file I/O)
    - No race conditions during build
    - Atomic operations
    """
    try:
        # Ensure table exists
        init_yaml_table()

        now = datetime.utcnow().isoformat() + "Z"

        # Upsert YAML content
        db.execute(
            """
            INSERT OR REPLACE INTO yaml_content (
                entity_type, entity_name, entity_id,
                yaml_content, created_at, updated_at
            ) VALUES (?, ?, ?, ?,
                COALESCE(
                    (SELECT created_at FROM yaml_content
                     WHERE entity_type = ? AND entity_name = ?),
                    ?
                ),
                ?
            )
        """,
            (
                entity_type,
                entity_name,
                entity_id,
                yaml_content,
                entity_type,  # For COALESCE subquery
                entity_name,  # For COALESCE subquery
                now,  # Default created_at if new
                now,  # updated_at
            ),
        )

        logger.debug(f"✅ Synced YAML for {entity_type}/{entity_name}")
        return True

    except Exception as e:
        logger.error(f"⚠️  Sync YAML error: {e}")
        return False


# ============================================================================
# QUERY HELPERS
# ============================================================================


def get_all_agents() -> List[Dict[str, Any]]:
    """Get all agents from SQLite"""
    try:
        rows = db.fetch_all(
            """
            SELECT
                agent_name, agent_id, subscription_id,
                entrypoint, description, version,
                inputs, outputs, tags, created_at, updated_at
            FROM agents
            ORDER BY agent_name
        """
        )

        agents = []
        for row in rows:
            agent = dict(row)
            agent["inputs"] = json.loads(agent["inputs"] or "[]")
            agent["outputs"] = json.loads(agent["outputs"] or "[]")
            agent["tags"] = json.loads(agent["tags"] or "[]")
            agents.append(agent)

        return agents

    except Exception as e:
        logger.error(f"Error fetching agents: {e}")
        return []


def get_all_chains() -> List[Dict[str, Any]]:
    """Get all chains from SQLite"""
    try:
        rows = db.fetch_all(
            """
            SELECT
                chain_name, chain_id, subscription_id,
                endpoint, method, description,
                steps, tags, created_at, updated_at
            FROM chains
            ORDER BY chain_name
        """
        )

        chains = []
        for row in rows:
            chain = dict(row)
            chain["steps"] = json.loads(chain["steps"] or "[]")
            chain["tags"] = json.loads(chain["tags"] or "[]")
            chains.append(chain)

        return chains

    except Exception as e:
        logger.error(f"Error fetching chains: {e}")
        return []


def get_recent_runs(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent runs from SQLite"""
    try:
        rows = db.fetch_all(
            """
            SELECT
                run_id, chain_name, chain_id,
                status, payload, results,
                created_at, completed_at,
                detached, success, cancelled
            FROM runs
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        runs = []
        for row in rows:
            run = dict(row)
            run["payload"] = json.loads(run["payload"] or "{}")
            run["results"] = json.loads(run["results"] or "[]")
            run["detached"] = bool(run["detached"])
            run["success"] = bool(run["success"])
            run["cancelled"] = bool(run["cancelled"])
            runs.append(run)

        return runs

    except Exception as e:
        logger.error(f"Error fetching runs: {e}")
        return []


def get_subscription() -> Optional[Dict[str, Any]]:
    """Get subscription from SQLite (Phase 1)"""
    try:
        row = db.fetch_one(
            """
            SELECT
                subscription_id, created_at, updated_at,
                status, plan, metadata
            FROM subscription
            LIMIT 1
        """
        )

        if not row:
            return None

        sub = dict(row)
        if sub.get("metadata"):
            sub["metadata"] = json.loads(sub["metadata"])

        return sub

    except Exception as e:
        logger.error(f"Error fetching subscription: {e}")
        return None


def get_subscription_id() -> Optional[str]:
    """Get just the subscription ID from SQLite (Phase 1)"""
    try:
        row = db.fetch_one("SELECT subscription_id FROM subscription LIMIT 1")
        return row["subscription_id"] if row else None
    except Exception as e:
        logger.error(f"Error fetching subscription ID: {e}")
        return None


def get_yaml(entity_type: str, entity_name: str) -> Optional[str]:
    """
    Get YAML content from SQLite cache (Phase 2)

    Args:
        entity_type: 'agent' or 'chain'
        entity_name: Name of the agent/chain

    Returns: YAML content as string, or None if not cached

    Usage:
        yaml = get_yaml('agent', 'knowledge_search')
        yaml = get_yaml('chain', 'customer_support')
    """
    try:
        row = db.fetch_one(
            """
            SELECT yaml_content, updated_at
            FROM yaml_content
            WHERE entity_type = ? AND entity_name = ?
        """,
            (entity_type, entity_name),
        )

        if not row:
            return None

        return row["yaml_content"]

    except Exception as e:
        logger.error(f"Error fetching YAML for {entity_type}/{entity_name}: {e}")
        return None


def cleanup_duplicate_subscriptions() -> int:
    """Remove duplicate subscriptions, keep oldest (Phase 1 fix)"""
    try:
        rows = db.fetch_all(
            """
            SELECT subscription_id, created_at
            FROM subscription
            ORDER BY created_at ASC
        """
        )

        if len(rows) <= 1:
            return 0

        oldest = rows[0]["subscription_id"]
        duplicates = [r["subscription_id"] for r in rows[1:]]

        for dup_id in duplicates:
            db.execute("DELETE FROM subscription WHERE subscription_id = ?", (dup_id,))
            logger.warning(f"Removed duplicate subscription: {dup_id}")

        logger.info(f"✅ Cleaned up {len(duplicates)} duplicate(s). Kept: {oldest}")
        return len(duplicates)

    except Exception as e:
        logger.error(f"Failed to cleanup duplicates: {e}")
        return 0


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    import sys

    print("📊 Initializing tables...")
    init_registry_tables()
    init_subscription_table()
    init_yaml_table()  # Phase 2
    print(f"✅ Database: {db.db_path}")
    print()

    if len(sys.argv) > 1:
        if sys.argv[1] == "sync":
            print("🔄 Syncing agents...")
            count = sync_agents()
            print(f"✅ Synced {count} agents\n")

            print("🔄 Syncing chains...")
            count = sync_chains()
            print(f"✅ Synced {count} chains\n")

            sub_file = Path(TH_ROOT) / "subscription_id.txt"
            if sub_file.exists():
                sub_id = sub_file.read_text().strip()
                print(f"🔄 Syncing subscription {sub_id}...")
                sync_subscription(sub_id)
                print("✅ Subscription synced")

        elif sys.argv[1] == "query":
            agents = get_all_agents()
            print(f"📋 Agents: {len(agents)}")
            for a in agents[:3]:
                print(f"  • {a['agent_name']}")
            print()

            chains = get_all_chains()
            print(f"⛓️  Chains: {len(chains)}")
            for c in chains[:3]:
                print(f"  • {c['chain_name']}")
            print()

            runs = get_recent_runs(5)
            print(f"🏃 Recent runs: {len(runs)}")
            print()

            sub = get_subscription()
            if sub:
                print(f"🔑 Subscription: {sub['subscription_id']}")
                print(f"   Status: {sub['status']}, Plan: {sub['plan']}")
    else:
        print("Usage:")
        print("  python sync_to_sqlite.py sync   # Sync all")
        print("  python sync_to_sqlite.py query  # Query database")

"""
TreehopperAI Workspace CLI Module

Ultra-simple: workspace = empty directory for development

Workspace = User's development folder (anywhere)
~/.treehopper = TreehopperAI's execution folder (managed separately)
"""

import sys
from pathlib import Path
from treehopper.logging import get_logger

logger = get_logger()


def workspace_create(workspace_name: str):
    """Create empty directory. Usage: th workspace create <n>"""

    workspace_path = Path.cwd() / workspace_name

    if workspace_path.exists():
        logger.warn(f"❌ Directory already exists: {workspace_path}")
        print(f"❌ Directory already exists: {workspace_path}")
        sys.exit(1)

    try:
        workspace_path.mkdir()
        print(f"✅ Workspace created: {workspace_name}")
        print(f"📁 {workspace_path}")
        print(f"\n💡 cd {workspace_name}")
        print("   th agent create my_agent --from-template email_listener")
        logger.info(f"Created: {workspace_path}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


def workspace_info():
    """Show current directory info. Usage: th workspace info"""

    current = Path.cwd()
    agents = [
        d.name for d in current.iterdir() if d.is_dir() and (d / "agent.yaml").exists()
    ]

    chains = []
    for f in current.glob("*.yaml"):
        try:
            import yaml

            if yaml.safe_load(f.read_text()).get("chain_name"):
                chains.append(f.stem)
        except Exception as e:
            print(f"[works[ace_info] error: {e}")
            logger.error(f"[works[ace_info] error: {e}")
            pass

    print(f"\n📦 {current.name}")
    print(f"📁 {current}")
    print(f"\n📂 Agents: {len(agents)}")
    for a in sorted(agents):
        print(f"   • {a}/")
    print(f"\n⛓️  Chains: {len(chains)}")
    for c in sorted(chains):
        print(f"   • {c}.yaml")
    print()

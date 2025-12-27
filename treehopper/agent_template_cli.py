"""
TreehopperAI Agent Template CLI Module

Provides template-based agent creation functionality.

Usage in treehopper_cli.py:
    from treehopper.agent_template_cli import (
        get_template_dirs,
        list_available_templates,
        load_template,
        agent_create_from_template,
        list_templates,
    )
"""

import sys
import uuid
from pathlib import Path
import importlib.util

from treehopper.th_config import TH_ROOT
from treehopper.utils.commons import get_or_create_subscription_id, validate_agent_name
from treehopper.logging import get_logger

logger = get_logger()


# ============================================================================
# TEMPLATE DISCOVERY
# ============================================================================


def get_template_dirs():
    """Get list of template directories to search"""
    template_dirs = []

    # Built-in templates (in package)
    package_templates = Path(__file__).parent / "agent_templates"
    if package_templates.exists():
        template_dirs.append(package_templates)

    # User templates (in TH_ROOT)
    user_templates = TH_ROOT / "templates"
    if user_templates.exists():
        template_dirs.append(user_templates)

    return template_dirs


def list_available_templates():
    """List all available templates with their paths"""
    templates = {}

    for template_dir in get_template_dirs():
        if not template_dir.exists():
            continue

        for template_file in template_dir.glob("*_template.py"):
            template_name = template_file.stem.replace("_template", "")
            templates[template_name] = template_file

    return templates


def load_template(template_name: str):
    """
    Load template by name.

    Returns dict with:
      - info: TEMPLATE_INFO
      - agent_yaml: AGENT_YAML string
      - handler_code: HANDLER_CODE string
      - schema_code: SCHEMA_CODE string

    Returns None if template not found.
    """
    templates = list_available_templates()

    if template_name not in templates:
        return None

    template_path = templates[template_name]

    try:
        # Load template module
        spec = importlib.util.spec_from_file_location(
            f"template_{template_name}", template_path
        )
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Extract sections
        template_data = {
            "info": getattr(module, "TEMPLATE_INFO", {}),
            "agent_yaml": getattr(module, "AGENT_YAML", ""),
            "handler_code": getattr(module, "HANDLER_CODE", ""),
            "schema_code": getattr(module, "SCHEMA_CODE", ""),
        }

        return template_data

    except Exception as e:
        logger.error(f"Failed to load template {template_name}: {e}")
        return None


# ============================================================================
# AGENT CREATION FROM TEMPLATE
# ============================================================================


def agent_create_from_template(agent_name: str, template_name: str):
    """
    Create agent from template in current directory.

    Args:
        agent_name: Name for the new agent
        template_name: Template to use (e.g., 'email_listener')

    Creates:
      <agent_name>/
        ├── agent.yaml
        ├── handler.py
        ├── schema.py
        └── __init__.py
    """

    # Validate agent name
    try:
        agent_name = validate_agent_name(agent_name)
    except ValueError as e:
        print(f"❌ {e}")
        logger.error(f"❌ {e}")
        sys.exit(1)

    # Check if agent folder already exists
    agent_dir = Path.cwd() / agent_name
    if agent_dir.exists():
        print(f"❌ Agent folder already exists: {agent_dir}")
        logger.error(f"❌ Agent folder already exists: {agent_dir}")
        sys.exit(1)

    # Load template
    print(f"📦 Loading template: {template_name}")
    logger.info(f"📦 Loading template: {template_name}")
    template_data = load_template(template_name)

    if not template_data:
        print(f"❌ Template not found: {template_name}")
        logger.error(f"❌ Template not found: {template_name}")
        print("\n📋 Available templates:")
        for name in list_available_templates().keys():
            print(f"  - {name}")
        sys.exit(1)

    # Generate IDs
    agent_id = f"{agent_name}-{uuid.uuid4().hex[:8]}"
    subscription_id = get_or_create_subscription_id()

    print(f"🆔 Generated agent_id: {agent_id}")
    print(f"🔑 Subscription ID: {subscription_id}")
    logger.info(f"🆔 Generated agent_id: {agent_id}")
    logger.info(f"🔑 Subscription ID: {subscription_id}")

    # Variable substitution
    variables = {
        "agent_name": agent_name,
        "agent_id": agent_id,
        "subscription_id": subscription_id,
    }

    agent_yaml = template_data["agent_yaml"].format(**variables)
    handler_code = template_data["handler_code"].format(**variables)
    schema_code = template_data["schema_code"]

    # Create agent directory
    agent_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Created directory: {agent_dir}")
    logger.info(f"📁 Created directory: {agent_dir}")

    # Write files
    (agent_dir / "agent.yaml").write_text(agent_yaml, encoding="utf-8")
    print("✅ Created: agent.yaml")
    logger.info("✅ Created: agent.yaml")

    (agent_dir / "handler.py").write_text(handler_code, encoding="utf-8")
    print("✅ Created: handler.py")
    logger.info("✅ Created: handler.py")

    (agent_dir / "schema.py").write_text(schema_code, encoding="utf-8")
    print("✅ Created: schema.py")
    logger.info("✅ Created: schema.py")

    (agent_dir / "__init__.py").write_text("", encoding="utf-8")
    print("✅ Created: __init__.py")
    logger.info("✅ Created: __init__.py")

    print("\n🎉 Agent created successfully!")
    print("\n📝 Next steps:")
    print(f"  1. Review and customize: {agent_dir}/handler.py")
    print(f"  2. Lint agent:           th agent lint {agent_name}")
    print(f"  3. Build agent:          th agent build {agent_name}")
    print(f"  4. Test agent:           th call {agent_name} '{{...}}'")

    logger.info("🎉 Agent created successfully!")


# ============================================================================
# LIST TEMPLATES COMMAND
# ============================================================================


def list_templates():
    """
    List all available templates.

    Shows template name, category, description, and tags.
    """
    templates = list_available_templates()

    if not templates:
        print("❌ No templates found")
        logger.info("❌ No templates found")
        return

    print(f"\n📦 Available Agent Templates ({len(templates)}):\n")
    logger.info(f"\n📦 Available Agent Templates ({len(templates)}):\n")

    for template_name, template_path in sorted(templates.items()):
        # Load template info
        template_data = load_template(template_name)

        if template_data:
            info = template_data["info"]
            category = info.get("category", "general")
            description = info.get("description", "")
            tags = ", ".join(info.get("tags", []))

            print(f"  📌 {template_name}")
            print(f"     Category: {category}")
            print(f"     Description: {description}")
            if tags:
                print(f"     Tags: {tags}")
            print()
        else:
            print(f"  📌 {template_name}")
            print(f"     Path: {template_path}")
            print()

    print("💡 Create agent: th agent create <name> --from-template <template>")
    logger.info("💡 Create agent: th agent create <name> --from-template <template>")

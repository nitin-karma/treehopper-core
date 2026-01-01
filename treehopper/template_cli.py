# treehopper/template_cli.py
# import os
# import sys
import shutil
import importlib.util
import re
from pathlib import Path
from typing import Dict, Any

from treehopper.logging import get_logger

logger = get_logger()

TEMPLATE_DIR = Path(__file__).parent / "agent_templates"


# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------


def _template_path(name: str) -> Path:
    if not name.endswith("_template.py"):
        name = f"{name}_template.py"
    return TEMPLATE_DIR / name


def _load_template(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path.name}")

        spec = importlib.util.spec_from_file_location("template_mod", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to initialize template loader for {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        required = ["TEMPLATE_INFO", "AGENT_YAML", "HANDLER_CODE", "SCHEMA_CODE"]
        for key in required:
            if not hasattr(module, key):
                raise ValueError(f"Missing required symbol: {key}")

        return {
            "TEMPLATE_INFO": module.TEMPLATE_INFO,
            "AGENT_YAML": module.AGENT_YAML,
            "HANDLER_CODE": module.HANDLER_CODE,
            "SCHEMA_CODE": module.SCHEMA_CODE,
        }

    except Exception as e:
        logger.exception("Failed to load template")
        print(f"❌ Failed to load template: {e}")
        return {}


# -------------------------------------------------------------------
# Linter
# -------------------------------------------------------------------

_ALLOWED_VARS = {"agent_name", "agent_id", "subscription_id"}


def _lint_template_path(path: Path) -> bool:
    try:
        tpl = _load_template(path)
        if not tpl:
            return False

        info = tpl["TEMPLATE_INFO"]

        # -----------------------------
        # Metadata checks
        # -----------------------------
        for k in ("name", "version", "category", "description", "author"):
            if k not in info:
                raise ValueError(f"TEMPLATE_INFO missing key: {k}")

        if not re.match(r"^\d+\.\d+\.\d+$", info["version"]):
            raise ValueError("TEMPLATE_INFO.version must be semver (X.Y.Z)")

        # -----------------------------
        # AGENT_YAML checks
        # -----------------------------
        yaml_text = tpl["AGENT_YAML"]
        if "inputs:" not in yaml_text or "outputs:" not in yaml_text:
            raise ValueError("AGENT_YAML must define inputs and outputs")

        for line in yaml_text.splitlines():
            if "source:" in line:
                src = line.split("source:", 1)[1].strip()
                if src.startswith("state.") and src.count(".") != 2:
                    raise ValueError(f"Invalid source format: {src}")

        # -----------------------------
        # HANDLER_CODE checks
        # -----------------------------
        handler = tpl["HANDLER_CODE"]

        bad_brace = re.search(r"{(?!agent_name|agent_id|subscription_id)", handler)
        if bad_brace:
            raise ValueError(
                "Unescaped { found in HANDLER_CODE. Use {{ }} for literals."
            )

        if "check_cancel" not in handler:
            raise ValueError("HANDLER_CODE must call await self.check_cancel()")

        print(f"✅ Template '{path.name}' passed lint checks")
        logger.info(f"Template '{path.name}' passed lint checks")
        return True

    except Exception as e:
        logger.exception("Template lint failed")
        print(f"❌ Template lint failed: {e}")
        return False


def lint_template(name: str) -> None:
    path = _template_path(name)

    if not path.exists():
        logger.info(f"❌ Template '{name}' not found in agent_templates")
        print(f"❌ Template '{name}' not found in agent_templates")
        return

    _lint_template_path(path)


# -------------------------------------------------------------------
# Deploy
# -------------------------------------------------------------------


def deploy_template(name: str) -> None:
    try:
        src = Path(name).expanduser().resolve()

        if not src.exists():
            print(f"[deploy_template] ❌ Template not found at: {src}")
            return

        if not src.name.endswith("_template.py"):
            print("❌ Template file must end with '_template.py'")
            return

        # 🔍 LINT SOURCE FIRST
        if not _lint_template_path(src):
            print("❌ Deployment aborted due to lint errors")
            return

        dst = TEMPLATE_DIR / src.name

        if dst.exists():
            ans = (
                input(f"⚠️ Template '{src.name}' already exists. Overwrite? (yes/no): ")
                .strip()
                .lower()
            )
            if ans != "yes":
                print("❌ Deploy aborted")
                return

        shutil.copyfile(src, dst)

        print(f"✅ Template '{src.name}' deployed successfully → {dst}")
        logger.info(f"Template '{src.name}' deployed")

    except Exception as e:
        logger.exception("Template deploy failed")
        print(f"❌ Template deploy failed: {e}")


# -------------------------------------------------------------------
# View
# -------------------------------------------------------------------


def view_template(name: str) -> None:
    try:
        path = _template_path(name)
        if not path.exists():
            print(f"❌ Template not found: {path.name}")
            return

        content = path.read_text()
        print(content)
        logger.info(f"Viewed template {path.name}")

    except Exception as e:
        logger.exception("Template view failed")
        print(f"❌ Failed to view template: {e}")


# -------------------------------------------------------------------
# List
# -------------------------------------------------------------------


def list_templates() -> None:
    try:
        if not TEMPLATE_DIR.exists():
            print("No templates directory found")
            return

        template_files = sorted(TEMPLATE_DIR.glob("*_template.py"))
        if not template_files:
            print("No templates available")
            return

        print("\n📦 Available Templates")
        print("────────────────────────────────────────────────────────")

        for path in template_files:
            name = path.stem.replace("_template", "")

            try:
                spec = importlib.util.spec_from_file_location("template_mod", path)
                if not (spec and spec.loader):
                    print(f"• {name}")
                    print("  └─ ⚠️  Invalid template file structure")
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                info = getattr(module, "TEMPLATE_INFO", {})

                t_name = info.get("name", name)
                version = info.get("version", "unknown")
                category = info.get("category", "uncategorized")
                desc = info.get("description", "").strip()

                print(f"• {t_name}")
                print(f"  ├─ version   : {version}")
                print(f"  ├─ category  : {category}")
                if desc:
                    print(f"  └─ desc      : {desc}")
                else:
                    print("  └─ desc      : (no description)")
                print()

            except Exception as e:
                # Do NOT fail listing due to one bad template
                logger.exception(
                    f"Failed loading template metadata: {path.name}, Error: {e}"
                )
                print(f"• {name}")
                print("  └─ ⚠️  Failed to load TEMPLATE_INFO (see logs)")
                print()

    except Exception as e:
        logger.exception("Template list failed")
        print(f"❌ Failed to list templates: {e}")


# -------------------------------------------------------------------
# Delete
# -------------------------------------------------------------------


def delete_template(name: str) -> None:
    try:
        path = _template_path(name)

        if not path.exists():
            print(f"❌ Template not found: {path.name}")
            return

        ans = input(
            f"⚠️ Deleting '{path.name}' is permanent. Type YES to confirm: "
        ).strip()

        if ans != "YES":
            print("❌ Delete aborted")
            return

        path.unlink()
        print(f"🗑️ Template '{path.name}' deleted")
        logger.info(f"Template '{path.name}' deleted")

    except Exception as e:
        logger.exception("Template delete failed")
        print(f"❌ Failed to delete template: {e}")


# -------------------------------------------------------------------
# Entry dispatcher
# -------------------------------------------------------------------


def template_entry(argv):
    try:
        if not argv:
            print("Usage: th template <lint|deploy|view|vu|list|delete> [name]")
            return

        action = argv[0]

        if action == "lint":
            lint_template(argv[1])
        elif action == "deploy":
            deploy_template(argv[1])
        elif action in ("view", "vu"):
            view_template(argv[1])
        elif action == "list":
            list_templates()
        elif action == "delete":
            delete_template(argv[1])
        else:
            print(f"❌ Unknown template command: {action}")

    except IndexError:
        print("❌ Missing template name")
    except Exception as e:
        logger.exception("Template command failed")
        print(f"❌ Template command failed: {e}")

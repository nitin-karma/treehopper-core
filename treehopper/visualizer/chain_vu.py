import yaml
import json
from pathlib import Path
from rich.console import Console
from rich.tree import Tree
from rich.syntax import Syntax
from treehopper.th_config import REGISTRY_DIR


def chain_flow_viewer(chain_name: str, raw_yaml: bool = False, raw_json: bool = False):
    """Parses chain.yaml and renders visual tree, raw YAML, or raw JSON."""

    chain_dir = Path(REGISTRY_DIR) / "chains"
    matches = list(chain_dir.glob(f"{chain_name}-*/chain.yaml"))

    if not matches:
        print(f"❌ Chain YAML not found for: {chain_name}")
        return

    yaml_path = matches[0]
    yaml_content = yaml_path.read_text()
    console = Console()

    # --- Mode 1: Raw YAML ---
    if raw_yaml:
        console.print(
            f"\n[bold cyan]📄 Raw YAML Source:[/bold cyan] [green]{yaml_path}[/green]\n"
        )
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
        return

    # Parse data for Tree or JSON
    try:
        data = yaml.safe_load(yaml_content)
    except Exception as e:
        print(f"❌ Error parsing YAML: {e}")
        return

    # --- Mode 2: Raw JSON ---
    if raw_json:
        console.print("\n[bold cyan]📋 Raw JSON Structure:[/bold cyan]\n")
        json_str = json.dumps(data, indent=4)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        console.print(syntax)
        return

    # --- Mode 3: Visual Tree (Default) ---
    console.print(
        f"\n[bold cyan]🔗 Chain Flow:[/bold cyan] [green]{chain_name}[/green]\n"
    )
    root = Tree("🚀 [bold]Entry Point[/bold]")

    if "agents" in data:
        for agent in data["agents"]:
            root.add(f"[bold emerald1]agent:[/bold emerald1] {agent['agent_name']}")
    elif "steps" in data:
        for step in data["steps"]:
            sid = step.get("step_id", "unknown")
            mode = step.get("execution_mode", "sequential")
            step_node = root.add(
                f"📦 [bold blue]Step:[/bold blue] {sid} [dim]({mode})[/dim]"
            )

            for agent in step.get("agents", []):
                step_node.add(
                    f"[bold emerald1]agent:[/bold emerald1] {agent['agent_name']}"
                )

            if "merge_agent" in step:
                step_node.add(
                    f"[bold orchid]merge-into:[/bold orchid] {step['merge_agent']}"
                )

            if "route_on" in step:
                route_branch = step_node.add("🚦 [bold amber3]route_on[/bold amber3]")
                for rule in step["route_on"]:
                    cond = rule.get("if", "condition")
                    target = rule.get("goto", "unknown")
                    route_branch.add(
                        f"[amber3]if {cond} ⮕ [/amber3][bold cyan]{target}[/bold cyan]"
                    )
    else:
        print("❌ Unsupported chain format.")
        return

    console.print(root)

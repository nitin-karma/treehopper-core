# treehopper/chain_build_parser.py
import json
from typing import List, Dict, Any
from treehopper.treehopper_chains import fail


def parse_build_steps_args(chain_name: str, args: List[str]) -> List[Dict[str, Any]]:
    """
    Parse --step CLI arguments into step definitions.
    This function is PURE (no IO, no registry writes).
    """

    steps = []
    i = 0

    while i < len(args):
        if args[i] != "--step":
            fail(f"Unexpected token: {args[i]}")

        if i + 3 >= len(args):
            fail("Invalid --step format")

        step_id = args[i + 1]
        mode = args[i + 2]
        step_agents = []

        j = i + 3
        merge_agent = None
        route_on = None

        while j < len(args) and args[j] != "--step":
            if args[j] == "--merge-agent":
                merge_agent = args[j + 1]
                j += 2
                continue

            if args[j] == "--route-on":
                try:
                    route_on = json.loads(args[j + 1])
                except Exception:
                    fail("Invalid JSON passed to --route-on")
                j += 2
                continue

            step_agents.append({"agent_name": args[j]})
            j += 1

        step_cfg = {
            "step_id": step_id,
            "execution_mode": mode,
            "agents": step_agents,
        }

        if merge_agent:
            step_cfg["merge_agent"] = merge_agent
        if route_on:
            step_cfg["route_on"] = route_on

        steps.append(step_cfg)
        i = j

    return steps

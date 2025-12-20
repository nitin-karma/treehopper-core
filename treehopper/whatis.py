from treehopper.th_config import VERSION, ASCII_BANNER


def print_whatis():
    print(ASCII_BANNER.format(version=VERSION))
    print(
        """
TreehopperAI is a local-first, agentic workflow engine for building
and executing intelligent chains of AI agents.

Core Concepts
─────────────
Agent     → Single AI capability, also runs as a service
Chain     → Workflow of agents, also runs as a service
Runtime   → Long-lived execution
Run       → One execution
Detached  → Background, cancellable runs
Replay    → Late joiner visibility

Common Commands
───────────────
treehopper run --bg
treehopper stop
treehopper status

treehopper init <agent1>
treehopper agent lint <agent1>
treehopper agent build <agent1>
treehopper chain build <chain> <agent1> <agent2>....
treehopper chain start <chain> --bg
treehopper chain run <chain> --payload '{...}'
treehopper chain cancel --run <RUN_ID>
treehopper chain resume <RUN_ID>

Use:
treehopper help
treehopper <command> --help
"""
    )

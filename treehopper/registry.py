# treehopper/registry.py
from treehopper.treehopper_cli import load_agents_index
from treehopper.treehopper_chains import load_chains_index

AGENT_REGISTRY = None
CHAIN_REGISTRY = None


def reload_registry():
    """
    Reload agents and chains from filesystem into in-process memory.
    This MUST be called after any CLI build commands in tests.
    """
    global AGENT_REGISTRY, CHAIN_REGISTRY
    AGENT_REGISTRY = load_agents_index()
    CHAIN_REGISTRY = load_chains_index()

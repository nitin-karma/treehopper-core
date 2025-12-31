# treehopper/chain_validation_rules.py

CHAIN_VALIDATION_RULES = [
    ("Chain metadata", "validate_chain_metadata"),
    ("Limits", "validate_limits"),
    ("Step structure", "validate_step_structure"),
    ("Agent existence", "validate_agent_existence"),
    ("Input resolution", "validate_input_resolution"),
    ("Merge rules", "validate_merge_rules"),
    ("Routing rules", "validate_routing_rules"),
]

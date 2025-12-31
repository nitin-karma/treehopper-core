# treehopper/chain_validator.py
from treehopper.treehopper_chains import (
    validate_chain_cfg,
    # validate_chain_metadata,
    # validate_limits,
    # validate_step_structure,
    # validate_agent_existence,
    # validate_input_resolution,
    # validate_merge_rules,
    # validate_routing_rules,
)
from treehopper.chain_build_parser import parse_build_steps_args
from treehopper.utils.commons import get_or_create_subscription_id
from treehopper.chain_validation_rules import CHAIN_VALIDATION_RULES
from treehopper.logging import get_logger

logger = get_logger()


def check_chain_cfg(cfg: dict) -> dict:
    """
    Backward compatibility normalizer.

    - If 'steps' already exists → NO-OP
    - If legacy 'agents' exists → convert to steps[]
    - Otherwise → error
    """

    # New-style chain (build-steps)
    if "steps" in cfg:
        return cfg

    # Legacy chain (chain build <name> a b c)
    agents = cfg.get("agents")
    if agents:
        steps = []
        for idx, agent in enumerate(agents):
            steps.append(
                {
                    "step_id": f"step_{idx + 1}",
                    "execution_mode": "sequential",
                    "agents": [agent],
                }
            )
        cfg["steps"] = steps
        return cfg

    raise ValueError("Invalid chain config: no steps or agents defined")


def validate_build_steps(chain_name: str, args: list):
    """
    Dry-run validation for `build-steps`.
    Does NOT write anything to disk.
    """

    steps = parse_build_steps_args(chain_name, args)

    cfg = {
        "chain_name": chain_name,
        "chain_id": "__dry_run__",
        "subscription_id": get_or_create_subscription_id(),
        "endpoint": f"/api/v1/chains/{chain_name}",
        "method": "POST",
        "steps": steps,
    }

    # Normalize for backward compatibility (safety)
    cfg = check_chain_cfg(cfg)

    # 🔒 SINGLE SOURCE OF TRUTH
    validate_chain_cfg(cfg)

    print("✅ Chain build-steps validation passed")


def validate_chain_cfg_explain(chain_name: str, args: list):
    print("\n🔍 Treehopper Chain Validation (Explain Mode)")
    print("────────────────────────────────────────────")

    steps = parse_build_steps_args(chain_name, args)

    cfg = {
        "chain_name": chain_name,
        "chain_id": "__dry_run__",
        "subscription_id": get_or_create_subscription_id(),
        "endpoint": f"/api/v1/chains/{chain_name}",
        "method": "POST",
        "steps": steps,
    }

    # Normalize for backward compatibility (safety)
    cfg = check_chain_cfg(cfg)

    for idx, (label, fn_name) in enumerate(CHAIN_VALIDATION_RULES, start=1):
        fn = globals().get(fn_name)
        if not fn:
            print(f"⚠️ Rule {idx}: {label} skipped (missing)")
            continue

        try:
            fn(cfg)
            print(f"✔ Rule {idx}: {label} valid")
        except SystemExit:
            # fail() already printed a detailed error
            print(f"✗ Rule {idx}: {label} FAILED")
            print("\nℹ️ Validation stopped at first failure\n")
            raise
        except Exception as e:
            print(f"✗ Rule {idx}: {label} FAILED")
            print(f"   Internal error: {e}")
            raise

    print("\n🎉 RESULT: Chain is VALID and safe to build\n")

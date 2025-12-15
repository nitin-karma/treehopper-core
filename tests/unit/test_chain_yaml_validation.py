import pytest
from treehopper.treehopper_chains import validate_chain_cfg
from unittest.mock import patch

# --- MOCK DATA ---
# This is a minimal specification required to satisfy the logic
# in validate_input_resolution (which checks the existence of keys).
MOCK_AGENT_SPEC = {
    "agent_name": "mock_agent",
    "inputs": [],
    "outputs": [],
    "entrypoint": "/mock",
    "description": "mocked for unit testing",
}

# --- FIXTURES: Valid YAML Structures (Corrected to use 'steps') ---

VALID_SIMPLE_CHAIN = {
    "chain_name": "valid_simple",
    "chain_id": "valid_simple-00000000",
    "subscription_id": "a75110fc-0cec-45fc-8ca7-edfe63744497",
    "endpoint": "/api/v1/chains/valid_simple",
    "method": "POST",
    # Using 'steps' to satisfy the internal structure expected by validate_limits
    "steps": [
        {
            "step_id": "step_0",
            "execution_mode": "sequential",
            "agents": [{"agent_name": "pdf_extractor", "path": "/path"}],
        }
    ],
    "description": "Simple sequential chain.",
}

VALID_STEP_CHAIN = {
    "chain_name": "valid_step",
    "chain_id": "valid_step-00000000",
    "subscription_id": "a75110fc-0cec-45fc-8ca7-edfe63744497",
    "endpoint": "/api/v1/chains/valid_step",
    "method": "POST",
    "steps": [
        {
            "step_id": "s1",
            "execution_mode": "sequential",
            "agents": [{"agent_name": "pdf_extractor", "path": "/path"}],
        }
    ],
    "description": "Step-based sequential chain.",
}

# =========================================================================
# 1. CORE CHAIN METADATA AND SYNTAX VALIDATION (MOCKED)
# =========================================================================


# We must patch all functions that perform external checks (existence, spec loading).
@patch("treehopper.treehopper_chains.validate_agent_existence")
@patch("treehopper.treehopper_chains.load_agent_spec")
def test_chain_valid_simple_format(mock_load_agent_spec, mock_validate_agent_existence):
    """
    Test a basic, valid chain configuration structure.
    Mocks agent checks to focus only on YAML structural validity.
    """
    # Ensure the mock returns a valid-looking spec when called by validate_input_resolution
    mock_load_agent_spec.return_value = MOCK_AGENT_SPEC

    # Should now pass, as all external dependencies are mocked out
    validate_chain_cfg(VALID_SIMPLE_CHAIN)


# =========================================================================
# 2. STRUCTURAL AND LOGIC VALIDATION (MOCKED)
# =========================================================================

# Apply patches to all relevant structural tests


@patch("treehopper.treehopper_chains.validate_agent_existence")
@patch("treehopper.treehopper_chains.load_agent_spec")
def test_chain_missing_required_field(
    mock_load_agent_spec, mock_validate_agent_existence
):
    """
    Test failure when a top-level required field like 'chain_name' is missing.
    Expected to raise KeyError when validation attempts to access the missing key.
    """
    mock_load_agent_spec.return_value = MOCK_AGENT_SPEC
    bad_chain = VALID_SIMPLE_CHAIN.copy()
    del bad_chain["chain_name"]

    # --- THE FIX ---
    # Change SystemExit to KeyError. Match is usually not needed for simple KeyErrors.
    with pytest.raises(ValueError, match="missing required field: 'chain_name'"):
        validate_chain_cfg(bad_chain)


@patch("treehopper.treehopper_chains.validate_agent_existence")
@patch("treehopper.treehopper_chains.load_agent_spec")
def test_chain_must_have_steps(mock_load_agent_spec, mock_validate_agent_existence):
    """Test failure when 'steps' is missing (assuming normalized format is expected)."""
    mock_load_agent_spec.return_value = MOCK_AGENT_SPEC
    bad_chain = VALID_SIMPLE_CHAIN.copy()
    del bad_chain["steps"]

    # Check for the specific error that the missing 'agents'/'steps' check throws
    with pytest.raises(ValueError, match="must contain a 'steps' list"):
        validate_chain_cfg(bad_chain)


@patch("treehopper.treehopper_chains.validate_agent_existence")
@patch("treehopper.treehopper_chains.load_agent_spec")
def test_step_invalid_execution_mode(
    mock_load_agent_spec, mock_validate_agent_existence
):
    """Test failure when 'execution_mode' is not 'sequential' or 'parallel'."""
    mock_load_agent_spec.return_value = MOCK_AGENT_SPEC
    bad_chain = VALID_STEP_CHAIN.copy()
    bad_chain["steps"][0]["execution_mode"] = "random"

    with pytest.raises(SystemExit):
        validate_chain_cfg(bad_chain)


@patch("treehopper.treehopper_chains.validate_agent_existence")
@patch("treehopper.treehopper_chains.load_agent_spec")
def test_chain_missing_merge_agent(mock_load_agent_spec, mock_validate_agent_existence):
    """
    Test failure when 'execution_mode' is 'parallel' but 'merge_agent' is missing.
    """
    mock_load_agent_spec.return_value = MOCK_AGENT_SPEC
    chain = {
        "chain_name": "demo",
        "chain_id": "demo-00000000",
        "subscription_id": "a75110fc-0cec-45fc-8ca7-edfe63744497",
        "endpoint": "/api/v1/chains/demo",
        "method": "POST",
        "steps": [
            {
                "step_id": "s1",
                "execution_mode": "parallel",  # Requires merge_agent
                "agents": [{"agent_name": "a1", "path": "/path"}],
                # merge_agent is missing
            }
        ],
    }
    with pytest.raises(SystemExit):
        validate_chain_cfg(chain)


@patch("treehopper.treehopper_chains.validate_agent_existence")
@patch("treehopper.treehopper_chains.load_agent_spec")
def test_chain_invalid_route_on_structure(
    mock_load_agent_spec, mock_validate_agent_existence
):
    """Test failure when 'route_on' is present but malformed (e.g., missing 'if')."""
    mock_load_agent_spec.return_value = MOCK_AGENT_SPEC
    bad_chain = VALID_STEP_CHAIN.copy()
    bad_chain["steps"][0]["route_on"] = [
        {"goto": "next_step"}  # Missing required 'if' key
    ]

    with pytest.raises(SystemExit):
        validate_chain_cfg(bad_chain)

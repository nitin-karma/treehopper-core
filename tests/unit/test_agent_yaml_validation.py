import pytest
from pathlib import Path

# NOTE: This assumes treehopper_cli is available in your environment's path
# and that the function signature is `validate_agent_yaml(agent_dir: Path) -> dict`
from treehopper.treehopper_cli import validate_agent_yaml

# --- YAML Definition for Testing Missing Fields ---
# This YAML is intentionally missing the 'entrypoint' field to cause a validation failure.
tmp_yaml = """
agent_name: test_ag
agent_id: test_ag-d1323e9b
subscription_id: a75110fc-0cec-45fc-8ca7-edfe63744497
# entrypoint: /test_ag  <-- MISSING
description: test_ag agent
inputs:
- name: name
  type: string
outputs:
- name: message
  type: string
tags: []
version: '1.0'

"""


def test_agent_yaml_missing_fields(tmp_path: Path):
    """
    Tests that validate_agent_yaml raises SystemExit (as implemented in the CLI)
    when a required field ('entrypoint') is missing from agent.yaml.
    """
    agent_dir = tmp_path / "bad_agent"
    agent_dir.mkdir()

    # Create the invalid agent.yaml file
    (agent_dir / "agent.yaml").write_text(tmp_yaml)

    # The function is implemented to raise SystemExit, so we must catch that.
    # The 'match' argument verifies the specific error message, confirming
    # the failure reason.
    with pytest.raises(
        SystemExit, match="agent.yaml missing required field: entrypoint"
    ):
        validate_agent_yaml(agent_dir)


# --- Optional: Test for Valid YAML ---
def test_agent_yaml_valid(tmp_path: Path):
    """
    Tests that validate_agent_yaml succeeds for a complete and valid YAML file.
    """
    valid_yaml = """
agent_name: valid_ag
agent_id: valid_ag-00000000
subscription_id: a75110fc-0cec-45fc-8ca7-edfe63744497
entrypoint: /valid_ag
description: valid_ag agent
inputs: []
outputs: []
tags: []
version: '1.0'
"""
    agent_dir = tmp_path / "good_agent"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text(valid_yaml)

    # Validation should pass without raising an exception.
    # We assert that the function returns a dictionary (the parsed data).
    data = validate_agent_yaml(agent_dir)
    assert isinstance(data, dict)
    assert data["agent_name"] == "valid_ag"

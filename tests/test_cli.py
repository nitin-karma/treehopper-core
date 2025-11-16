import subprocess

def test_cli_run_agent():
    result = subprocess.run(
        ["treehopper", "call", "/greet", '{"name": "Test"}'],
        capture_output=True, text=True
    )
    assert "Test" in result.stdout

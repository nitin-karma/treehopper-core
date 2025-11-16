import pytest
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["TREEHOPPER_AUTODISCOVERY"] = "0"

@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set fake API keys so code depending on .env still works in tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
    monkeypatch.setenv("XAI_API_KEY", "test_key")
    monkeypatch.setenv("GEMINI_API_KEY", "test_key")


class FakeLLM:
    """Mock LLM provider response for deterministic tests."""
    def chat(self, prompt, **kwargs):
        return f"MOCK_RESPONSE: {prompt}"


@pytest.fixture
def fake_llm():
    return FakeLLM()

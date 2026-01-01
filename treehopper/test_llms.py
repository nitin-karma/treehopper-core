"""
Test cases for TreehopperAI LLM providers
Tests: OpenAI, Perplexity, Gemini, Claude

Run with: pytest test_llm_providers.py -v
"""

import os
import pytest
import asyncio
from treehopper.treehopper_llm import call_llm

# =============================================================================
# SETUP INSTRUCTIONS
# =============================================================================
"""
BEFORE RUNNING TESTS:

1. Create a .env file in the project root with your API keys:

    # OpenAI
    OPENAI_API_KEY=sk-...

    # Perplexity
    PERPLEXITY_API_KEY=pplx-...

    # Google Gemini
    GEMINI_API_KEY=...

    # Anthropic Claude
    ANTHROPIC_API_KEY=sk-ant-...

2. Optional: Configure models (defaults are already set)

    # OpenAI (default: gpt-4o-mini)
    TH_OPENAI_MODEL=gpt-4o-mini
    TH_OPENAI_TEMPERATURE=0.6

    # Perplexity (default: mistral-7b-instruct)
    TH_PERPLEXITY_MODEL=mistral-7b-instruct

    # Gemini (default: gemini-pro)
    # Uses gemini-pro by default

    # Claude (default: claude-3-5-sonnet-20241022)
    TH_CLAUDE_MODEL=claude-3-5-sonnet-20241022
    TH_CLAUDE_MAX_TOKENS=1024
    TH_CLAUDE_TEMPERATURE=0.6

3. Install dependencies:
    pip install pytest pytest-asyncio httpx python-dotenv

4. Run tests:
    pytest test_llm_providers.py -v

    # Run specific provider
    pytest test_llm_providers.py::test_openai -v
    pytest test_llm_providers.py::test_perplexity -v
    pytest test_llm_providers.py::test_gemini -v
    pytest test_llm_providers.py::test_claude -v

    # Run with output
    pytest test_llm_providers.py -v -s

5. Skip providers you don't have keys for:
    pytest test_llm_providers.py -v -k "not perplexity"
"""

# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# API KEY VALIDATION
# =============================================================================


def check_api_key(provider: str) -> tuple[bool, str]:
    """Check if API key is configured for a provider"""
    key_map = {
        "openai": "OPENAI_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
    }

    env_var = key_map.get(provider.lower())
    if not env_var:
        return False, f"Unknown provider: {provider}"

    key = os.getenv(env_var)
    if not key:
        return False, f"Missing {env_var} in .env file"

    # Basic validation
    if provider == "openai" and not key.startswith("sk-"):
        return False, f"{env_var} should start with 'sk-'"
    if provider == "perplexity" and not key.startswith("pplx-"):
        return False, f"{env_var} should start with 'pplx-'"
    if provider == "claude" and not key.startswith("sk-ant-"):
        return False, f"{env_var} should start with 'sk-ant-'"

    return True, "OK"


# =============================================================================
# TEST CASE 1: OPENAI
# =============================================================================


@pytest.mark.asyncio
async def test_openai():
    """Test OpenAI provider (GPT-4o-mini)"""

    # Check API key
    has_key, msg = check_api_key("openai")
    if not has_key:
        pytest.skip(f"Skipping OpenAI test: {msg}")

    print("\n" + "=" * 60)
    print("🧪 TEST: OpenAI (GPT-4o-mini)")
    print("=" * 60)

    # Test prompt
    prompt = "What is 2+2? Answer in one word."

    # Call LLM
    result = await call_llm(prompt, provider="openai")

    # Assertions
    print(f"\n✅ Response: {result.get('message', 'N/A')}")
    print(f"📊 Tokens: {result.get('tokens', 0)}")
    print(f"⏱️  Latency: {result.get('latency', 0)}s")

    assert "error" not in result, f"OpenAI returned error: {result.get('error')}"
    assert "message" in result, "Response missing 'message' field"
    assert len(result["message"]) > 0, "Response message is empty"
    assert result["tokens"] > 0, "Token count should be > 0"
    assert result["latency"] > 0, "Latency should be > 0"

    # Check if answer contains "4" or "four"
    answer = result["message"].lower()
    assert "4" in answer or "four" in answer, f"Unexpected answer: {result['message']}"

    print("\n✅ OpenAI test PASSED")


# =============================================================================
# TEST CASE 2: PERPLEXITY
# =============================================================================


@pytest.mark.asyncio
async def test_perplexity():
    """Test Perplexity provider (Mistral-7b-instruct)"""

    # Check API key
    has_key, msg = check_api_key("perplexity")
    if not has_key:
        pytest.skip(f"Skipping Perplexity test: {msg}")

    print("\n" + "=" * 60)
    print("🧪 TEST: Perplexity (Mistral-7b-instruct)")
    print("=" * 60)

    # Test prompt
    prompt = "What is the capital of France? Answer in one word."

    # Call LLM
    result = await call_llm(prompt, provider="perplexity")

    # Assertions
    print(f"\n✅ Response: {result.get('message', 'N/A')}")
    print(f"📊 Tokens: {result.get('tokens', 0)}")
    print(f"⏱️  Latency: {result.get('latency', 0)}s")

    assert "error" not in result, f"Perplexity returned error: {result.get('error')}"
    assert "message" in result, "Response missing 'message' field"
    assert len(result["message"]) > 0, "Response message is empty"
    assert result["tokens"] >= 0, "Token count should be >= 0"
    assert result["latency"] > 0, "Latency should be > 0"

    # Check if answer contains "Paris"
    answer = result["message"].lower()
    assert "paris" in answer, f"Unexpected answer: {result['message']}"

    print("\n✅ Perplexity test PASSED")


# =============================================================================
# TEST CASE 3: GEMINI
# =============================================================================


@pytest.mark.asyncio
async def test_gemini():
    """Test Google Gemini provider (Gemini-Pro)"""

    # Check API key
    has_key, msg = check_api_key("gemini")
    if not has_key:
        pytest.skip(f"Skipping Gemini test: {msg}")

    print("\n" + "=" * 60)
    print("🧪 TEST: Google Gemini (Gemini-Pro)")
    print("=" * 60)

    # Test prompt
    prompt = "What is the largest planet in our solar system? Answer in one word."

    # Call LLM
    result = await call_llm(prompt, provider="gemini")

    # Assertions
    print(f"\n✅ Response: {result.get('message', 'N/A')}")
    print(f"📊 Tokens: {result.get('tokens', 0)}")
    print(f"⏱️  Latency: {result.get('latency', 0)}s")

    assert "error" not in result, f"Gemini returned error: {result.get('error')}"
    assert "message" in result, "Response missing 'message' field"
    assert len(result["message"]) > 0, "Response message is empty"
    assert result["tokens"] >= 0, "Token count should be >= 0"
    assert result["latency"] > 0, "Latency should be > 0"

    # Check if answer contains "Jupiter"
    answer = result["message"].lower()
    assert "jupiter" in answer, f"Unexpected answer: {result['message']}"

    print("\n✅ Gemini test PASSED")


# =============================================================================
# TEST CASE 4: CLAUDE (NEW)
# =============================================================================


@pytest.mark.asyncio
async def test_claude():
    """Test Anthropic Claude provider (Claude-3.5-Sonnet)"""

    # Check API key
    has_key, msg = check_api_key("claude")
    if not has_key:
        pytest.skip(f"Skipping Claude test: {msg}")

    print("\n" + "=" * 60)
    print("🧪 TEST: Anthropic Claude (Claude-3.5-Sonnet)")
    print("=" * 60)

    # Test prompt
    prompt = (
        "What is the speed of light in vacuum? Answer with just the number and unit."
    )

    # Call LLM
    result = await call_llm(prompt, provider="claude")

    # Assertions
    print(f"\n✅ Response: {result.get('message', 'N/A')}")
    print(f"📊 Tokens: {result.get('tokens', 0)}")
    print(f"⏱️  Latency: {result.get('latency', 0)}s")

    assert "error" not in result, f"Claude returned error: {result.get('error')}"
    assert "message" in result, "Response missing 'message' field"
    assert len(result["message"]) > 0, "Response message is empty"
    assert result["tokens"] > 0, "Token count should be > 0"
    assert result["latency"] > 0, "Latency should be > 0"

    # Check if answer contains speed of light
    answer = result["message"].lower()
    # Should contain some variant of 299,792,458 m/s or 3×10^8 m/s
    assert (
        "299" in answer or "3" in answer or "300" in answer
    ), f"Unexpected answer: {result['message']}"

    print("\n✅ Claude test PASSED")


# =============================================================================
# TEST CASE 5: ERROR HANDLING
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_api_key():
    """Test that invalid API key returns proper error"""

    print("\n" + "=" * 60)
    print("🧪 TEST: Invalid API Key Handling")
    print("=" * 60)

    # Test with obviously invalid key
    result = await call_llm("test", provider="openai", api_key="invalid-key-12345")

    print(f"\n✅ Error response: {result.get('error', 'N/A')}")

    assert "error" in result, "Should return error for invalid API key"
    assert result["tokens"] == 0, "Token count should be 0 on error"
    assert result["latency"] > 0, "Latency should still be recorded"

    print("\n✅ Error handling test PASSED")


# =============================================================================
# TEST CASE 6: UNSUPPORTED PROVIDER
# =============================================================================


@pytest.mark.asyncio
async def test_unsupported_provider():
    """Test that unsupported provider returns proper error"""

    print("\n" + "=" * 60)
    print("🧪 TEST: Unsupported Provider")
    print("=" * 60)

    result = await call_llm("test", provider="unknown-provider")

    print(f"\n✅ Error response: {result.get('error', 'N/A')}")

    assert "error" in result, "Should return error for unsupported provider"
    assert "Unsupported provider" in result["error"]
    assert result["tokens"] == 0
    assert result["latency"] > 0

    print("\n✅ Unsupported provider test PASSED")


# =============================================================================
# TEST CASE 7: MOCK PROVIDER
# =============================================================================


@pytest.mark.asyncio
async def test_mock_provider():
    """Test mock provider (for CI/testing)"""

    print("\n" + "=" * 60)
    print("🧪 TEST: Mock Provider")
    print("=" * 60)

    result = await call_llm("test prompt", provider="mock")

    print(f"\n✅ Response: {result.get('message', 'N/A')}")
    print(f"⏱️  Latency: {result.get('latency', 0)}s")

    assert "error" not in result
    assert result["message"] == "[MOCK] quick response"
    assert result["tokens"] == 0
    assert result["latency"] > 0

    print("\n✅ Mock provider test PASSED")


# =============================================================================
# MAIN (for running without pytest)
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🧪 TreehopperAI LLM Provider Tests")
    print("=" * 70)
    print("\nNOTE: Run with pytest for best results:")
    print("  pytest test_llm_providers.py -v")
    print("\nRunning basic async test...\n")

    async def run_basic_test():
        # Test mock provider (no API key needed)
        result = await call_llm("Hello!", provider="mock")
        print(f"Mock test result: {result}")

    asyncio.run(run_basic_test())

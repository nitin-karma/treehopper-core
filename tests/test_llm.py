import pytest
from unittest.mock import AsyncMock, patch
from treehopper.treehopper_llm import call_llm

pytestmark = pytest.mark.asyncio  # applies to entire module


async def test_call_openai():
    with patch("treehopper.treehopper_llm.call_openai", new_callable=AsyncMock) as mock:
        mock.return_value = "OK_OPENAI"
        result = await call_llm("Hello", provider="openai")
        assert result == "OK_OPENAI"
        mock.assert_awaited_once()


async def test_call_perplexity():
    with patch(
        "treehopper.treehopper_llm.call_perplexity", new_callable=AsyncMock
    ) as mock:
        mock.return_value = "OK_PPLX"
        result = await call_llm("Hello", provider="perplexity")
        assert result == "OK_PPLX"
        mock.assert_awaited_once()


async def test_call_gemini():
    with patch("treehopper.treehopper_llm.call_gemini", new_callable=AsyncMock) as mock:
        mock.return_value = "OK_GEMINI"
        result = await call_llm("Hello", provider="gemini")
        assert result == "OK_GEMINI"
        mock.assert_awaited_once()


async def test_llm_unsupported_provider():
    result = await call_llm("Hello", provider="unknown")
    assert result.startswith("Unsupported provider")

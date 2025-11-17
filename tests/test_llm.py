import pytest
from unittest.mock import AsyncMock, patch
from treehopper.treehopper_llm import call_llm

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_call_openai():
    with patch("treehopper.treehopper_llm.call_openai", new_callable=AsyncMock) as mock:
        mock.return_value = {"message": "OK_OPENAI", "tokens": 0}
        result = await call_llm("Hello", provider="openai")
        assert result["message"] == "OK_OPENAI"


@pytest.mark.asyncio
async def test_call_perplexity():
    with patch(
        "treehopper.treehopper_llm.call_perplexity", new_callable=AsyncMock
    ) as mock:
        mock.return_value = {"message": "OK_PPLX", "tokens": 0}
        result = await call_llm("Hello", provider="perplexity")
        assert result["message"] == "OK_PPLX"


@pytest.mark.asyncio
async def test_call_gemini():
    with patch("treehopper.treehopper_llm.call_gemini", new_callable=AsyncMock) as mock:
        mock.return_value = {"message": "OK_GEMINI", "tokens": 0}
        result = await call_llm("Hello", provider="gemini")
        assert result["message"] == "OK_GEMINI"


@pytest.mark.asyncio
async def test_llm_unsupported_provider():
    result = await call_llm("Hello", provider="unknown")
    assert "Unsupported provider" in result["error"]

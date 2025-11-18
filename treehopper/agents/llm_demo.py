# agents/llm_test.py
from typing import Optional
from treehopper.treehopper import agent
from treehopper.treehopper_llm import call_llm


@agent("/api/v1/agents/llm/test", method="POST", goal="Test LLM provider connectivity")
async def llm_test(provider: str = "openai", api_key: Optional[str] = None):
    try:
        response = await call_llm("Say hello from Treehopper", provider, api_key)
        return {"provider": provider, "status": "success", "response": response}
    except Exception as e:
        return {"provider": provider, "status": "error", "message": str(e)}

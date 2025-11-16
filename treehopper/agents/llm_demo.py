# agents/llm_test.py

from treehopper.treehopper import agent
from treehopper.treehopper_llm import call_llm

@agent("/llm/test", method="POST", goal="Test LLM provider connectivity", tags=["llm"])
async def llm_test(provider: str = "openai", api_key: str = None):
    try:
        response = await call_llm("Say hello from Treehopper", provider, api_key)
        return {"provider": provider, "status": "success", "response": response}
    except Exception as e:
        return {"provider": provider, "status": "error", "message": str(e)}

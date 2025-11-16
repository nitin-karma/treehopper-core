# agents/llm_compare.py
from treehopper.treehopper import agent
from treehopper.treehopper_llm import call_llm


@agent(
    "/api/v1/agents/llm/compare",
    method="POST",
    goal="Compare LLM responses across providers",
    tags=["Example Agents"],
)
async def llm_compare(prompt: str, api_keys: dict):
    results = {}
    for provider, key in api_keys.items():
        try:
            response = await call_llm(prompt, provider, key)
            results[provider] = {"status": "success", "response": response}
        except Exception as e:
            results[provider] = {"status": "error", "message": str(e)}
    return {"prompt": prompt, "results": results}

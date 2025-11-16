# agents/llm_providers.py
from treehopper.treehopper import agent


@agent(
    "/llm/providers",
    method="GET",
    goal="List supported LLM providers",
    tags=["Example Agents"],
)
async def llm_providers():
    return {
        "providers": [
            {"name": "openai", "models": ["gpt-4", "gpt-3.5-turbo"]},
            {"name": "perplexity", "models": ["mistral-7b-instruct"]},
            {"name": "gemini", "models": ["gemini-pro"]},
        ]
    }

# agents/prompt_agent.py
from typing import Optional
from treehopper.treehopper import agent
from treehopper.treehopper_llm import call_llm


@agent(
    "/api/v1/agents/prompt",
    method="POST",
    goal="Respond to prompt using LLM",
    tags=["Example Agents"],
)
async def prompt_agent(
    prompt: str, provider: str = "openai", api_key: Optional[str] = None
):
    response = await call_llm(prompt, provider, api_key)
    return {"response": response}

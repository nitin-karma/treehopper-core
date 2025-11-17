# agents/llm_compare.py
from treehopper.treehopper import agent
from pydantic import BaseModel
from fastapi import Body


class LLMCompareRequest(BaseModel):
    prompt: str


@agent(
    "llm_compare",
    method="POST",
    goal="Compare responses from multiple LLMs",
    tags=["Example Agents"],
)
async def llm_compare(req: LLMCompareRequest = Body(...), prompt: str | None = None):
    """
    Accepts:
    - HTTP body {"prompt": "..."}
    - Chaining params {"prompt": "..."}
    """
    text = prompt if prompt is not None else req.prompt
    return {"compare": f"LLM comparison placeholder for prompt '{text}'"}

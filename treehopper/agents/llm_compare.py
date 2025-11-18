from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from pydantic import BaseModel


class CompareRequest(BaseModel):
    prompt: str


class CompareAgent:
    async def run(self, prompt: str) -> dict:
        return {"summary": f"Compared: {prompt}"}


@agent("llm_compare", method="POST", goal="Compare LLM responses")
async def handle(
    request: CompareRequest = Body(..., embed=False)  # 🚨 embed=False is critical
):
    ag = CompareAgent()
    return JSONResponse(await ag.run(request.prompt))

# quality_evaluator_template.py

TEMPLATE_INFO = {
    "name": "quality_evaluator",
    "version": "1.0.0",
    "category": "evaluation",
    "description": "Evaluates quality of generated responses",
    "author": "TreehopperAI",
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Quality evaluator
inputs:
  - name: text
    type: string
outputs:
  - name: score
    type: number
  - name: safe
    type: boolean
version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from .schema import QualityRequest, QualityResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

class QualityEvaluatorAgent(TreehopperAgentBase):
    async def run(self, request: QualityRequest) -> QualityResponse:
        await self.check_cancel()

        text = request.text or ""
        score = min(len(text) / 200.0, 1.0)
        safe = len(text.strip()) > 0

        return QualityResponse(
            score=score,
            safe=safe,
            success=True
        )

@agent("{agent_name}", method="POST", goal="Quality evaluation")
async def handle(payload: QualityRequest = Body(...)):
    agent = QualityEvaluatorAgent()
    return (await agent.run(payload)).dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional

class QualityRequest(BaseModel):
    text: Optional[str] = ""

class QualityResponse(BaseModel):
    score: float = 0.0
    safe: bool = True
    success: bool = True
    error: Optional[str] = None
"""

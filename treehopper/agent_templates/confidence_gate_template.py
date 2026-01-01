# confidence_gate_template.py

TEMPLATE_INFO = {
    "name": "confidence_gate",
    "version": "1.0.0",
    "category": "control",
    "description": "Blocks or allows chain execution based on confidence threshold",
    "author": "TreehopperAI",
    "use_cases": [
        "Skip LLM on low confidence",
        "Prevent bad automation",
        "Human-in-the-loop gating",
    ],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Confidence based gate
inputs:
  - name: confidence
    type: number
  - name: threshold
    type: number
    default: 0.7
outputs:
  - name: allowed
    type: boolean
  - name: confidence
    type: number
version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from .schema import ConfidenceGateRequest, ConfidenceGateResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

class ConfidenceGateAgent(TreehopperAgentBase):
    async def run(self, request: ConfidenceGateRequest) -> ConfidenceGateResponse:
        await self.check_cancel()

        confidence = request.confidence or 0.0
        threshold = request.threshold or 0.7

        allowed = confidence >= threshold

        return ConfidenceGateResponse(
            allowed=allowed,
            confidence=confidence,
            success=True
        )

@agent("{agent_name}", method="POST", goal="Confidence gate")
async def handle(payload: ConfidenceGateRequest = Body(...)):
    agent = ConfidenceGateAgent()
    return (await agent.run(payload)).dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional

class ConfidenceGateRequest(BaseModel):
    confidence: Optional[float] = 0.0
    threshold: Optional[float] = 0.7

class ConfidenceGateResponse(BaseModel):
    allowed: bool = False
    confidence: float = 0.0
    success: bool = True
    error: Optional[str] = None
"""

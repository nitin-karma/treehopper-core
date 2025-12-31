"""
Template: Analysis Bridge
Category: Logic & Control
Description: Normalizes analysis outputs (intent, urgency, confidence)
             into a stable schema independent of agent instance names.

Use Cases:
  - Decouple routers from classifier versions
  - Stabilize sequential and parallel chains
  - Avoid state.classify.classifier_cX coupling
"""

TEMPLATE_INFO = {
    "name": "analysis_bridge",
    "version": "1.0.0",
    "category": "logic_control",
    "description": "Stabilizes analysis outputs across steps and agent versions",
    "author": "TreehopperAI",
    "tags": ["bridge", "normalization", "analysis"],
    "dependencies": [],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Normalize analysis outputs into stable fields

inputs:
  - name: state
    type: object
    description: Full chain state snapshot

outputs:
  - name: intent
    type: string
    description: Normalized intent
  - name: urgency
    type: string
    description: Normalized urgency
  - name: confidence
    type: number
    description: Normalized confidence

tags:
  - bridge
  - normalization
version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from typing import Dict, Any, Optional

from treehopper.treehopper import agent
from treehopper.agent_base import TreehopperAgentBase

from .schema import AnalysisBridgeRequest, AnalysisBridgeResponse


class AnalysisBridgeAgent(TreehopperAgentBase):
    '''
    Extracts intent, urgency, and confidence from upstream steps
    without relying on agent instance names.
    '''

    def _extract_first(self, step_data: Dict[str, Any], key: str) -> Optional[Any]:
        if not isinstance(step_data, dict):
            return None
        for _, agent_output in step_data.items():
            if isinstance(agent_output, dict) and key in agent_output:
                return agent_output.get(key)
        return None

    async def run(self, request: AnalysisBridgeRequest) -> AnalysisBridgeResponse:
        try:
            state = request.state or {{}}

            classify = state.get("classify", {{}})
            detect = state.get("detect", {{}})

            intent = self._extract_first(classify, "intent")
            confidence = self._extract_first(classify, "confidence")
            urgency = self._extract_first(detect, "urgency")

            return AnalysisBridgeResponse(
                intent=intent,
                urgency=urgency,
                confidence=confidence,
                success=True
            )

        except Exception as e:
            return AnalysisBridgeResponse(
                intent=None,
                urgency=None,
                confidence=None,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Normalize analysis outputs")
async def handle(payload: AnalysisBridgeRequest = Body(...)):
    agent_instance = AnalysisBridgeAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""


SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class AnalysisBridgeRequest(BaseModel):
    state: Optional[Dict[str, Any]] = Field(
        None, description="Full chain state snapshot (optional)"
    )


class AnalysisBridgeResponse(BaseModel):
    intent: Optional[str] = None
    urgency: Optional[str] = None
    confidence: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
"""

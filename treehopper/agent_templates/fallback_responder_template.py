# fallback_responder_template.py

TEMPLATE_INFO = {
    "name": "fallback_responder",
    "version": "1.0.0",
    "category": "output_delivery",
    "description": "Fallback response when automation fails",
    "author": "TreehopperAI",
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Fallback responder
inputs:
  - name: message
    type: string
outputs:
  - name: response
    type: string
version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from .schema import FallbackRequest, FallbackResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

class FallbackResponderAgent(TreehopperAgentBase):
    async def run(self, request: FallbackRequest) -> FallbackResponse:
        await self.check_cancel()

        return FallbackResponse(
            response=request.message or "We are looking into this.",
            success=True
        )

@agent("{agent_name}", method="POST", goal="Fallback response")
async def handle(payload: FallbackRequest = Body(...)):
    agent = FallbackResponderAgent()
    return (await agent.run(payload)).dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional

class FallbackRequest(BaseModel):
    message: Optional[str] = "We are looking into this."

class FallbackResponse(BaseModel):
    response: str = ""
    success: bool = True
    error: Optional[str] = None
"""

# decision_router_template.py

TEMPLATE_INFO = {
    "name": "decision_router",
    "version": "1.0.0",
    "category": "control",
    "description": "Maps inputs to routing decisions",
    "author": "TreehopperAI",
    "use_cases": [
        "Business routing",
        "Support escalation",
        "Workflow branching",
    ],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Decision router
inputs:
  - name: intent
    type: string
  - name: urgency
    type: string
outputs:
  - name: route
    type: string
  - name: reasoning
    type: string
version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from .schema import DecisionRouterRequest, DecisionRouterResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

class DecisionRouterAgent(TreehopperAgentBase):
    async def run(self, request: DecisionRouterRequest) -> DecisionRouterResponse:
        await self.check_cancel()

        intent = request.intent or "unknown"
        urgency = request.urgency or "low"

        if urgency == "critical":
            route = "escalate"
            reasoning = "Critical urgency"
        else:
            route = "auto_respond"
            reasoning = "Safe to auto respond"

        return DecisionRouterResponse(
            route=route,
            reasoning=reasoning,
            success=True
        )

@agent("{agent_name}", method="POST", goal="Decision routing")
async def handle(payload: DecisionRouterRequest = Body(...)):
    agent = DecisionRouterAgent()
    return (await agent.run(payload)).dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional

class DecisionRouterRequest(BaseModel):
    intent: Optional[str] = None
    urgency: Optional[str] = None

class DecisionRouterResponse(BaseModel):
    route: str = "auto_respond"
    reasoning: str = ""
    success: bool = True
    error: Optional[str] = None
"""

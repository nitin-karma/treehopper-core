"""
Template: Simple Router
Category: Logic & Control
Description: Make routing decisions based on analysis

Use Cases:
  - Workflow routing
  - Escalation decisions
  - Priority classification
"""

TEMPLATE_INFO = {
    "name": "simple_router",
    "version": "1.0.0",
    "category": "logic_control",
    "description": "Route messages based on analysis",
    "author": "TreehopperAI",
    "tags": ["routing", "logic", "decision"],
    "dependencies": [],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Route based on intent and urgency
inputs:
  - name: intent
    type: string
    source: state.classify.intent

  - name: urgency
    type: string
    source: state.analyze.urgency

  - name: confidence
    type: number
    source: state.analyze.confidence

outputs:
  - name: route
    type: string
    description: Routing decision (auto_respond/escalate/vip_priority)
  - name: reasoning
    type: string
    description: Why this route
tags:
  - routing
  - decision
version: '1.0'
"""

HANDLER_CODE = """import asyncio
from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import SimpleRouterRequest, SimpleRouterResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class SimpleRouterAgent(TreehopperAgentBase):
    '''Simple routing logic'''

    ESCALATE_INTENTS = {{"bug_report", "complaint", "refund_request"}}

    async def run(self, request: SimpleRouterRequest) -> SimpleRouterResponse:
        await self.check_cancel()

        intent = request.intent
        urgency = request.urgency
        confidence = request.confidence

        if urgency == "critical":
            return SimpleRouterResponse(
                route="escalate",
                reasoning="Critical urgency requires immediate human attention"
            )

        if confidence < 0.6:
            return SimpleRouterResponse(
                route="escalate",
                reasoning=f"Low confidence ({{confidence:.2f}}) - needs human review"
            )

        if intent in self.ESCALATE_INTENTS and urgency in ["high", "critical"]:
            return SimpleRouterResponse(
                route="escalate",
                reasoning="High-risk intent requires escalation"
            )

        return SimpleRouterResponse(
            route="auto_respond",
            reasoning="Straightforward query can be auto-handled"
        )



@agent("{agent_name}", method="POST", goal="Route message to appropriate handler")
async def handle(payload: SimpleRouterRequest = Body(...)):
    agent_instance = SimpleRouterAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional


class SimpleRouterRequest(BaseModel):
    '''Input schema for simple router'''
    intent: str = Field(..., description="Classified intent")
    urgency: str = Field(..., description="Urgency level")
    confidence: float = Field(..., description="Confidence score", ge=0, le=1)


class SimpleRouterResponse(BaseModel):
    '''Output schema for simple router'''
    route: str = Field(..., description="Routing decision")
    reasoning: str = Field(..., description="Why this route")
    success: bool = Field(True)
    error: Optional[str] = None
"""

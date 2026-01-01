"""
Template: Memory Gate
Category: Control
Description: Skip expensive downstream steps if memory already has a confident hit
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "memory_gate",
    "version": "1.0.0",
    "category": "control",
    "description": (
        "Decision gate that evaluates memory results and determines whether "
        "downstream LLM or reasoning steps should be skipped."
    ),
    "author": "TreehopperAI",
    "tags": ["memory", "gate", "optimization", "cost-control"],
    "dependencies": [],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Skip LLM if memory hit is confident
inputs:
  - name: hit
    type: boolean
  - name: confidence
    type: number
outputs:
  - name: proceed
    type: boolean
  - name: reason
    type: string
version: "1.0"
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import MemoryGateRequest, MemoryGateResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class MemoryGateAgent(TreehopperAgentBase):
    async def run(self, request: MemoryGateRequest) -> MemoryGateResponse:
        await self.check_cancel()

        hit = bool(request.hit)
        confidence = float(request.confidence or 0.0)

        if hit and confidence >= 0.75:
            return MemoryGateResponse(
                proceed=False,
                reason="Memory hit is confident; skipping LLM",
                success=True,
            )

        return MemoryGateResponse(
            proceed=True,
            reason="Memory miss or low confidence; proceeding",
            success=True,
        )


@agent("{agent_name}", method="POST", goal="Gate downstream steps using memory confidence")
async def handle(payload: MemoryGateRequest = Body(...)):
    agent = MemoryGateAgent()
    return (await agent.run(payload)).dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional


class MemoryGateRequest(BaseModel):
    hit: bool
    confidence: Optional[float] = 0.0


class MemoryGateResponse(BaseModel):
    proceed: bool = True
    reason: str = ""
    success: bool = True
    error: Optional[str] = None
"""

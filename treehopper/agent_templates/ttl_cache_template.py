"""
Template: TTL Cache
Category: Control
Description: Time-based cache validity evaluator
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "ttl_cache",
    "version": "1.0.0",
    "category": "control",
    "description": (
        "Evaluates whether cached data is still valid based on TTL. "
        "Used to prevent stale memory or state reuse."
    ),
    "author": "TreehopperAI",
    "tags": ["cache", "ttl", "time", "control"],
    "dependencies": [],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: TTL-based cache validation
inputs:
  - name: timestamp
    type: string
  - name: ttl_seconds
    type: number
outputs:
  - name: valid
    type: boolean
version: "1.0"
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """from datetime import datetime
from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import TTLCacheRequest, TTLCacheResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class TTLCacheAgent(TreehopperAgentBase):
    async def run(self, request: TTLCacheRequest) -> TTLCacheResponse:
        await self.check_cancel()

        try:
            ts = datetime.fromisoformat(request.timestamp.replace("Z", ""))
            ttl = float(request.ttl_seconds)
            age = (datetime.utcnow() - ts).total_seconds()

            return TTLCacheResponse(
                valid=age <= ttl,
                success=True,
            )

        except Exception:
            return TTLCacheResponse(
                valid=False,
                success=False,
                error="Invalid timestamp",
            )


@agent("{agent_name}", method="POST", goal="Validate cache using TTL")
async def handle(payload: TTLCacheRequest = Body(...)):
    agent = TTLCacheAgent()
    return (await agent.run(payload)).dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional


class TTLCacheRequest(BaseModel):
    timestamp: str
    ttl_seconds: float


class TTLCacheResponse(BaseModel):
    valid: bool = False
    success: bool = True
    error: Optional[str] = None
"""

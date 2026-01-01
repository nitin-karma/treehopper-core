# schema_normalizer_template.py

TEMPLATE_INFO = {
    "name": "schema_normalizer",
    "version": "1.0.1",
    "category": "transform",
    "description": "Normalizes arbitrary agent outputs into a predictable schema",
    "author": "TreehopperAI",
    "use_cases": [
        "Downstream safety",
        "Schema alignment",
        "Enterprise workflows",
    ],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Schema normalizer
inputs:
  - name: data
    type: object
outputs:
  - name: normalized
    type: object
version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from .schema import NormalizeRequest, NormalizeResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

class SchemaNormalizerAgent(TreehopperAgentBase):
    async def run(self, request: NormalizeRequest) -> NormalizeResponse:
        await self.check_cancel()

        data = request.data or dict()
        normalized = dict(data)

        return NormalizeResponse(
            normalized=normalized,
            success=True
        )

@agent("{agent_name}", method="POST", goal="Schema normalization")
async def handle(payload: NormalizeRequest = Body(...)):
    agent = SchemaNormalizerAgent()
    return (await agent.run(payload)).dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional, Dict, Any

class NormalizeRequest(BaseModel):
    data: Optional[Dict[str, Any]] = None

class NormalizeResponse(BaseModel):
    normalized: Dict[str, Any] = dict()
    success: bool = True
    error: Optional[str] = None
"""

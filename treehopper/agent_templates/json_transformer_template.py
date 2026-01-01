# json_transformer_template.py

TEMPLATE_INFO = {
    "name": "json_transformer",
    "version": "1.0.1",
    "category": "transform",
    "description": "Safely transforms JSON payloads without side effects",
    "author": "TreehopperAI",
    "use_cases": [
        "JSON reshaping",
        "Pipeline compatibility",
        "Agent interoperability",
    ],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: JSON transformer
inputs:
  - name: data
    type: object
outputs:
  - name: data
    type: object
version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from .schema import JSONTransformRequest, JSONTransformResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

class JSONTransformerAgent(TreehopperAgentBase):
    async def run(self, request: JSONTransformRequest) -> JSONTransformResponse:
        await self.check_cancel()

        data = request.data or dict()

        return JSONTransformResponse(
            data=data,
            success=True
        )

@agent("{agent_name}", method="POST", goal="JSON transform")
async def handle(payload: JSONTransformRequest = Body(...)):
    agent = JSONTransformerAgent()
    return (await agent.run(payload)).dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional, Dict, Any

class JSONTransformRequest(BaseModel):
    data: Optional[Dict[str, Any]] = None

class JSONTransformResponse(BaseModel):
    data: Dict[str, Any] = dict()
    success: bool = True
    error: Optional[str] = None
"""

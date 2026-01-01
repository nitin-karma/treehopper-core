# retry_controller_template.py

TEMPLATE_INFO = {
    "name": "retry_controller",
    "version": "1.0.0",
    "category": "resilience",
    "description": "Controls retry behavior for unstable steps",
    "author": "TreehopperAI",
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Retry controller
inputs:
  - name: attempt
    type: number
  - name: max_attempts
    type: number
    default: 3
outputs:
  - name: retry
    type: boolean
version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from .schema import RetryRequest, RetryResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

class RetryControllerAgent(TreehopperAgentBase):
    async def run(self, request: RetryRequest) -> RetryResponse:
        await self.check_cancel()

        attempt = request.attempt or 0
        max_attempts = request.max_attempts or 3

        retry = attempt < max_attempts

        return RetryResponse(
            retry=retry,
            success=True
        )

@agent("{agent_name}", method="POST", goal="Retry control")
async def handle(payload: RetryRequest = Body(...)):
    agent = RetryControllerAgent()
    return (await agent.run(payload)).dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional

class RetryRequest(BaseModel):
    attempt: Optional[int] = 0
    max_attempts: Optional[int] = 3

class RetryResponse(BaseModel):
    retry: bool = False
    success: bool = True
    error: Optional[str] = None
"""

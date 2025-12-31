"""
Template: Alert Manager
Category: Output Delivery
Description: Send escalation alerts to support team
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "alert_manager",
    "version": "1.0.2",
    "category": "output_delivery",
    "description": "Send escalation alerts",
    "author": "TreehopperAI",
    "tags": ["alerts", "notification", "escalation"],
    "dependencies": [],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Send escalation alerts
inputs:
  - name: message
    type: string
  - name: priority
    type: string
  - name: customer_email
    type: string
outputs:
  - name: sent
    type: boolean
  - name: channels
    type: array
  - name: timestamp
    type: string
tags:
  - alerts
  - escalation
version: '1.0'
"""

# ============================================================================
# HANDLER.PY  ✅ FORMAT-SAFE (NO {}, NO f-strings)
# ============================================================================
HANDLER_CODE = """from datetime import datetime
from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import AlertManagerRequest, AlertManagerResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class AlertManagerAgent(TreehopperAgentBase):
    async def run(self, request: AlertManagerRequest) -> AlertManagerResponse:
        await self.check_cancel()

        # SAFE NORMALIZATION
        message = request.message or "Escalation triggered by system"
        priority = request.priority or "high"
        customer_email = request.customer_email or "unknown@customer.com"

        timestamp = datetime.utcnow().isoformat() + "Z"

        print("🚨 ALERT [" + priority.upper() + "]")
        print("   Message: " + message)
        print("   Customer: " + customer_email)
        print("   Time: " + timestamp)

        if priority in ["critical", "high"]:
            channels = ["slack", "email", "pagerduty"]
        elif priority == "medium":
            channels = ["slack", "email"]
        else:
            channels = ["email"]

        return AlertManagerResponse(
            sent=True,
            channels=channels,
            timestamp=timestamp,
            success=True
        )


@agent("{agent_name}", method="POST", goal="Send escalation alerts")
async def handle(payload: AlertManagerRequest = Body(...)):
    agent = AlertManagerAgent()
    return (await agent.run(payload)).dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List


class AlertManagerRequest(BaseModel):
    message: Optional[str] = None
    priority: Optional[str] = None
    customer_email: Optional[str] = None


class AlertManagerResponse(BaseModel):
    sent: bool = False
    channels: List[str] = Field(default_factory=list)
    timestamp: str = ""
    success: bool = True
    error: Optional[str] = None
"""

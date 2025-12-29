"""
Template: Alert Manager
Category: Output Delivery
Description: Send escalation alerts to support team

Use Cases:
  - Escalation notifications
  - Critical alerts
  - Team notifications
"""

TEMPLATE_INFO = {
    "name": "alert_manager",
    "version": "1.0.0",
    "category": "output_delivery",
    "description": "Send escalation alerts",
    "author": "TreehopperAI",
    "tags": ["alerts", "notification", "escalation"],
    "dependencies": [],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Send escalation alerts
inputs:
  - name: message
    type: string
    description: Alert message
    source: request
  - name: priority
    type: string
    description: Alert priority (low/medium/high/critical)
    source: request
  - name: customer_email
    type: string
    description: Customer email
    source: request
outputs:
  - name: sent
    type: boolean
    description: Alert sent successfully
  - name: channels
    type: array
    description: Channels alerted
  - name: timestamp
    type: string
    description: When alert was sent
tags:
  - alerts
  - escalation
version: '1.0'
"""

HANDLER_CODE = """import asyncio
from datetime import datetime
from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import AlertManagerRequest, AlertManagerResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class AlertManagerAgent(TreehopperAgentBase):
    '''Alert manager for escalations'''

    async def run(self, request: AlertManagerRequest) -> AlertManagerResponse:
        await self.check_cancel()

        try:
            # Mock alert sending (in real system, send to Slack/PagerDuty/etc)
            channels = []
            timestamp = datetime.utcnow().isoformat() + "Z"

            # Log the alert
            print(f"🚨 ALERT [{request.priority.upper()}]")
            print(f"   Message: {request.message}")
            print(f"   Customer: {request.customer_email}")
            print(f"   Time: {timestamp}")

            # Determine channels based on priority
            if request.priority in ["critical", "high"]:
                channels = ["slack", "email", "pagerduty"]
            elif request.priority == "medium":
                channels = ["slack", "email"]
            else:
                channels = ["email"]

            await self.check_cancel()

            return AlertManagerResponse(
                sent=True,
                channels=channels,
                timestamp=timestamp,
                success=True
            )

        except Exception as e:
            return AlertManagerResponse(
                sent=False,
                channels=[],
                timestamp="",
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Send escalation alerts")
async def handle(payload: AlertManagerRequest = Body(...)):
    agent_instance = AlertManagerAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List


class AlertManagerRequest(BaseModel):
    '''Input schema for alert manager'''
    message: str = Field(..., description="Alert message", min_length=1)
    priority: str = Field("medium", description="Alert priority")
    customer_email: str = Field("", description="Customer email")


class AlertManagerResponse(BaseModel):
    '''Output schema for alert manager'''
    sent: bool = Field(False)
    channels: List[str] = Field(default_factory=list)
    timestamp: str = Field("")
    success: bool = Field(True)
    error: Optional[str] = None
"""

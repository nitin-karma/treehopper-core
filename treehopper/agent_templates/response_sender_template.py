"""
Template: Response Sender
Category: Output Delivery
Description: Send responses via email, Slack, or SMS

Use Cases:
  - Automated email replies
  - Slack notifications
  - Multi-channel communication
"""

TEMPLATE_INFO = {
    "name": "response_sender",
    "version": "1.1.0",
    "category": "output_delivery",
    "description": "Multi-channel response delivery (email/Slack/SMS)",
    "author": "TreehopperAI",
    "tags": ["output", "email", "slack", "notification"],
    "dependencies": ["smtplib", "httpx"],
}

# ---------------------------------------------------------------------
# AGENT YAML
# ---------------------------------------------------------------------

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Send responses via email, Slack, or SMS

# sender_c5 AGENT_YAML (CORRECT PLACE)
inputs:
  - name: recipient
    source: state.enrich.recipient

  - name: response
    source: state.respond.response

  - name: channel
    source: state.enrich.channel

  - name: subject
    source: state.enrich.subject

  - name: priority
    source: state.enrich.priority



outputs:
  - name: sent
    type: boolean
    description: Message sent successfully

  - name: message_id
    type: string
    description: Delivery confirmation ID

  - name: channel_used
    type: string
    description: Channel used for delivery

tags:
  - output
  - email
  - slack
version: '1.1'
"""

# ---------------------------------------------------------------------
# HANDLER CODE
# ---------------------------------------------------------------------

HANDLER_CODE = """from datetime import datetime
from fastapi import Body
import httpx

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import ResponseSenderRequest, ResponseSenderResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class ResponseSenderAgent(TreehopperAgentBase):
    '''Multi-channel response sender (simulation-safe)'''

    async def _simulate_send(self, channel: str, message: str):
        await self.check_cancel()
        timestamp = datetime.utcnow().isoformat() + "Z"
        return ResponseSenderResponse(
            sent=True,
            message_id=f"sim-{{channel}}-{{int(datetime.utcnow().timestamp())}}",
            channel_used=channel,
            timestamp=timestamp,
            success=True
        )

    async def run(self, request: ResponseSenderRequest) -> ResponseSenderResponse:
        await self.check_cancel()

        # -------------------------------------------------
        # Normalize inputs (CRITICAL)
        # -------------------------------------------------
        message = request.message or request.response
        if not message:
            return ResponseSenderResponse(
                sent=False,
                success=False,
                error="No message or response provided to sender"
            )

        channel = (request.channel or "email").lower()
        priority = request.priority or "medium"

        # -------------------------------------------------
        # Auto-detect channel if missing
        # -------------------------------------------------
        if not request.channel:
            if "@" in request.recipient:
                channel = "email"
            else:
                channel = "slack"

        # -------------------------------------------------
        # SIMULATION MODE (default for Chain 5)
        # -------------------------------------------------
        if channel in ["email", "slack", "sms"]:
            return await self._simulate_send(channel, message)

        # -------------------------------------------------
        # Unsupported channel
        # -------------------------------------------------
        return ResponseSenderResponse(
            sent=False,
            success=False,
            error=f"Unsupported channel: {{channel}}"
        )


@agent("{agent_name}", method="POST", goal="Send response via email, Slack, or SMS")
async def handle(payload: ResponseSenderRequest = Body(...)):
    agent_instance = ResponseSenderAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

# ---------------------------------------------------------------------
# SCHEMA
# ---------------------------------------------------------------------

SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional


class EmailConfig(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    from_email: str
    from_name: str = "Support Team"
    use_tls: bool = True


class SlackConfig(BaseModel):
    webhook_url: str
    username: str = "Support Bot"
    icon_emoji: Optional[str] = ":robot_face:"


class ResponseSenderRequest(BaseModel):
    recipient: str
    message: Optional[str] = None
    response: Optional[str] = None
    channel: Optional[str] = "email"
    subject: Optional[str] = None
    priority: Optional[str] = "medium"
    email_config: Optional[EmailConfig] = None
    slack_config: Optional[SlackConfig] = None


class ResponseSenderResponse(BaseModel):
    sent: bool = False
    message_id: str = ""
    channel_used: str = ""
    timestamp: str = ""
    success: bool = True
    error: Optional[str] = None
"""

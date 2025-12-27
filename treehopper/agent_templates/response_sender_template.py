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
    "version": "1.0.0",
    "category": "output_delivery",
    "description": "Multi-channel response delivery (email/Slack/SMS)",
    "author": "TreehopperAI",
    "tags": ["output", "email", "slack", "notification"],
    "dependencies": ["smtplib", "httpx"],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Send responses via email, Slack, or SMS
inputs:
  - name: recipient
    type: string
    description: Recipient email/phone/channel
  - name: message
    type: string
    description: Message content
  - name: channel
    type: string
    description: Delivery channel (email/slack/sms)
  - name: subject
    type: string
    description: Email subject
  - name: priority
    type: string
    description: Priority (low/medium/high/urgent)
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
version: '1.0'
"""

HANDLER_CODE = """import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from fastapi import Body
import httpx

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import ResponseSenderRequest, ResponseSenderResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class ResponseSenderAgent(TreehopperAgentBase):
    '''Multi-channel response sender'''

    async def _send_email(self, recipient, message, subject, email_config):
        try:
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = f"{{email_config.from_name}} <{{email_config.from_email}}>"
            msg["To"] = recipient
            msg.attach(MIMEText(message, "plain"))

            await self.check_cancel()

            if email_config.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(email_config.smtp_username, email_config.smtp_password)
                    server.sendmail(email_config.from_email, [recipient], msg.as_string())
            else:
                with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port) as server:
                    server.login(email_config.smtp_username, email_config.smtp_password)
                    server.sendmail(email_config.from_email, [recipient], msg.as_string())

            message_id = f"<{{datetime.utcnow().timestamp()}}@{{email_config.smtp_host}}>"
            return True, message_id, ""
        except Exception as e:
            return False, "", str(e)

    async def _send_slack(self, message, slack_config, priority):
        try:
            payload = {{
                "text": message,
                "username": slack_config.username
            }}

            if slack_config.icon_emoji:
                payload["icon_emoji"] = slack_config.icon_emoji

            if priority in ["high", "urgent"]:
                payload["text"] = f"🚨 *{{priority.upper()}}* 🚨\\n\\n{{message}}"

            await self.check_cancel()

            async with httpx.AsyncClient() as client:
                response = await client.post(slack_config.webhook_url, json=payload, timeout=10.0)

                if response.status_code == 200:
                    message_id = f"slack-{{datetime.utcnow().timestamp()}}"
                    return True, message_id, ""
                else:
                    return False, "", f"Slack API error: {{response.status_code}}"
        except Exception as e:
            return False, "", str(e)

    async def run(self, request: ResponseSenderRequest) -> ResponseSenderResponse:
        await self.check_cancel()

        try:
            channel = request.channel.lower()
            timestamp = datetime.utcnow().isoformat() + "Z"

            if channel == "email":
                if not request.email_config:
                    return ResponseSenderResponse(
                        sent=False,
                        channel_used="email",
                        success=False,
                        error="Email configuration required"
                    )

                subject = request.subject or "Support Response"
                success, msg_id, error = await self._send_email(
                    request.recipient,
                    request.message,
                    subject,
                    request.email_config
                )

                if success:
                    return ResponseSenderResponse(
                        sent=True,
                        message_id=msg_id,
                        channel_used="email",
                        timestamp=timestamp,
                        success=True
                    )
                else:
                    return ResponseSenderResponse(
                        sent=False,
                        channel_used="email",
                        success=False,
                        error=f"Email delivery failed: {{error}}"
                    )

            elif channel == "slack":
                if not request.slack_config:
                    return ResponseSenderResponse(
                        sent=False,
                        channel_used="slack",
                        success=False,
                        error="Slack configuration required"
                    )

                success, msg_id, error = await self._send_slack(
                    request.message,
                    request.slack_config,
                    request.priority
                )

                if success:
                    return ResponseSenderResponse(
                        sent=True,
                        message_id=msg_id,
                        channel_used="slack",
                        timestamp=timestamp,
                        success=True
                    )
                else:
                    return ResponseSenderResponse(
                        sent=False,
                        channel_used="slack",
                        success=False,
                        error=f"Slack delivery failed: {{error}}"
                    )

            else:
                return ResponseSenderResponse(
                    sent=False,
                    success=False,
                    error=f"Unsupported channel: {{channel}}"
                )

        except Exception as e:
            return ResponseSenderResponse(
                sent=False,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Send response via email, Slack, or SMS")
async def handle(payload: ResponseSenderRequest = Body(...)):
    agent_instance = ResponseSenderAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

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
    message: str = Field(..., min_length=1)
    channel: str = Field("email")
    subject: Optional[str] = None
    priority: str = Field("medium")
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

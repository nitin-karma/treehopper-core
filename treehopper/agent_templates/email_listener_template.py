"""
Template: Email Listener
Category: Data Ingestion
Description: Fetch emails from IMAP/Gmail for support automation

Use Cases:
  - Customer support ticket ingestion
  - Newsletter processing
  - Email-based workflow automation
  - Support queue monitoring
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "email_listener",
    "version": "1.0.0",
    "category": "data_ingestion",
    "description": "Email listener with IMAP support for support automation",
    "author": "TreehopperAI",
    "tags": ["email", "imap", "support", "automation"],
    "dependencies": ["imaplib", "email"],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Email listener agent for support automation
inputs:
  - name: email_config
    type: object
    description: Email server configuration (host, port, username, password)
  - name: folder
    type: string
    description: Mail folder to read from (default INBOX)
  - name: limit
    type: integer
    description: Maximum emails to fetch
  - name: unread_only
    type: boolean
    description: Only fetch unread emails
outputs:
  - name: emails
    type: array
    description: List of email objects with subject, sender, body
  - name: count
    type: integer
    description: Number of emails fetched
  - name: success
    type: boolean
    description: Operation success status
tags:
  - email
  - imap
  - automation
  - support
version: '1.0'
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """import asyncio
import imaplib
import email
from email.header import decode_header
from typing import List
from fastapi import Body
from pathlib import Path

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.runtime_context import get_run_id
from treehopper.treehopper_cancellation import is_run_cancelled

from .schema import EmailListenerRequest, EmailListenerResponse, EmailMessage, EmailConfig

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class EmailListenerAgent(TreehopperAgentBase):
    '''Email listener with IMAP support'''

    def _decode_header(self, header: str) -> str:
        '''Decode email header (handles encoding)'''
        if not header:
            return ""

        decoded_parts = decode_header(header)
        result = []

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or 'utf-8', errors='ignore'))
            else:
                result.append(str(part))

        return " ".join(result)

    def _extract_email_address(self, from_header: str) -> tuple:
        '''Extract name and email from From header'''
        if '<' in from_header and '>' in from_header:
            name = from_header.split('<')[0].strip().strip('"')
            email_addr = from_header.split('<')[1].split('>')[0].strip()
            return name, email_addr
        else:
            return "", from_header.strip()

    def _get_email_body(self, msg) -> tuple:
        '''Extract plain text and HTML body from email'''
        plain_text = ""
        html_text = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                try:
                    body = part.get_payload(decode=True)
                    if body:
                        body = body.decode('utf-8', errors='ignore')

                        if content_type == "text/plain":
                            plain_text = body
                        elif content_type == "text/html":
                            html_text = body
                except Exception:
                    continue
        else:
            try:
                body = msg.get_payload(decode=True)
                if body:
                    plain_text = body.decode('utf-8', errors='ignore')
            except Exception:
                pass

        return plain_text, html_text

    async def run(self, request: EmailListenerRequest) -> EmailListenerResponse:
        '''Fetch emails from IMAP server'''
        await self.check_cancel()

        try:
            config = request.email_config

            # Connect to IMAP
            if config.use_ssl:
                mail = imaplib.IMAP4_SSL(config.host, config.port)
            else:
                mail = imaplib.IMAP4(config.host, config.port)

            mail.login(config.username, config.password)

            # Select folder
            status, _ = mail.select(request.folder)
            if status != 'OK':
                return EmailListenerResponse(
                    emails=[],
                    count=0,
                    success=False,
                    error=f"Failed to select folder: {{request.folder}}"
                )

            # Search emails
            search_criteria = "UNSEEN" if request.unread_only else "ALL"
            status, messages = mail.search(None, search_criteria)

            if status != 'OK':
                return EmailListenerResponse(
                    emails=[],
                    count=0,
                    success=False,
                    error="Failed to search emails"
                )

            email_ids = messages[0].split()
            email_ids = email_ids[-request.limit:] if email_ids else []

            await self.check_cancel()

            # Fetch emails
            emails = []
            for i, email_id in enumerate(email_ids):
                if i % 5 == 0:
                    await self.check_cancel()

                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extract fields
                subject = self._decode_header(msg.get("Subject", ""))
                from_header = self._decode_header(msg.get("From", ""))
                sender_name, sender_email = self._extract_email_address(from_header)
                date_str = msg.get("Date", "")

                # Get body
                plain_body, html_body = self._get_email_body(msg)

                emails.append(EmailMessage(
                    subject=subject,
                    sender=sender_name or sender_email,
                    sender_email=sender_email,
                    body=plain_body,
                    date=date_str
                ))

            mail.close()
            mail.logout()

            return EmailListenerResponse(
                emails=emails,
                count=len(emails),
                success=True
            )

        except Exception as e:
            return EmailListenerResponse(
                emails=[],
                count=0,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Fetch emails from IMAP/Gmail server")
async def handle(payload: EmailListenerRequest = Body(...)):
    '''FastAPI handler for email listener'''
    agent_instance = EmailListenerAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List


class EmailConfig(BaseModel):
    '''Email server configuration'''
    host: str = Field(..., description="IMAP server host (e.g., imap.gmail.com)")
    port: int = Field(993, description="IMAP port (default 993 for SSL)")
    username: str = Field(..., description="Email username/address")
    password: str = Field(..., description="Email password or app password")
    use_ssl: bool = Field(True, description="Use SSL connection")


class EmailMessage(BaseModel):
    '''Single email message'''
    subject: str
    sender: str
    sender_email: str
    body: str
    date: str


class EmailListenerRequest(BaseModel):
    '''Input schema for email listener'''
    email_config: EmailConfig = Field(..., description="Email server configuration")
    folder: str = Field("INBOX", description="Mail folder to read from")
    limit: int = Field(10, description="Maximum emails to fetch", ge=1, le=100)
    unread_only: bool = Field(True, description="Only fetch unread emails")


class EmailListenerResponse(BaseModel):
    '''Output schema for email listener'''
    emails: List[EmailMessage] = Field(default_factory=list)
    count: int = Field(0, description="Number of emails fetched")
    success: bool = Field(True, description="Operation success")
    error: Optional[str] = Field(None, description="Error message if failed")
"""

"""
Template: Context Enricher
Category: Logic & Control
Description: Normalizes multi-source input (Email, Chat, CLI) into a standard schema.

Use Cases:
  - Flattening email lists for LLM processing
  - Mapping disparate input keys to a unified chain state
  - Default value injection for optional parameters
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "context_enricher",
    "version": "1.0.0",
    "category": "logic_control",
    "description": "Generic data normalizer and context builder",
    "author": "TreehopperAI",
    "tags": ["logic", "mapping", "normalization", "utility"],
    "dependencies": [],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Standardizes input data for downstream agents
inputs:
  - name: text
    type: string
    description: Raw text input (CLI/Chat)
  - name: emails
    type: array
    description: List of email objects (from email_listener)
  - name: metadata
    type: object
    description: Optional metadata for context enrichment
outputs:
  - name: customer_message
    type: string
    description: Standardized message text
  - name: query
    type: string
    description: Cleaned search query
  - name: recipient
    type: string
    description: Standardized recipient identifier
  - name: session_context
    type: object
    description: Dictionary of enrichment metadata
tags:
  - logic
  - normalization
version: '1.0'
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """import asyncio
from fastapi import Body
from typing import Dict, Any, List, Optional

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import EnricherRequest, EnricherResponse

class ContextEnricherAgent(TreehopperAgentBase):
    async def run(self, request: EnricherRequest) -> EnricherResponse:
        try:
            # Doubled braces {{ }} are escaped literals for the .format() method
            context = {{}}
            final_message = ""
            final_recipient = ""

            # Check for Email Source
            if request.emails and len(request.emails) > 0:
                first_email = request.emails[0]
                final_message = first_email.body
                final_recipient = first_email.sender_email
                context = {{
                    "source": "email",
                    "count": len(request.emails),
                    "original_subject": first_email.get("subject", "")
                }}

            # Fallback to Text/CLI Source
            elif request.text:
                final_message = request.text
                final_recipient = "cli_user"
                context = {{"source": "direct_text"}}

            # Merge manual metadata if provided
            if request.metadata:
                context.update(request.metadata)

            # Generate a simplified search query (first 10 words)
            search_query = " ".join(final_message.split()[:10])

            return EnricherResponse(
                customer_message=final_message,
                query=search_query,
                recipient=final_recipient,
                session_context=context,
                success=True
            )
        except Exception as e:
            return EnricherResponse(
                customer_message="",
                query="",
                recipient="",
                session_context={{}},
                success=False,
                error=str(e)
            )

@agent("{agent_name}", method="POST", goal="Normalize data for support chains")
async def handle(payload: EnricherRequest = Body(...)):
    agent_instance = ContextEnricherAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class EnricherRequest(BaseModel):
    text: Optional[str] = Field(None, description="Direct text input")
    emails: Optional[List[Dict[str, Any]]] = Field(None, description="List of email objects")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class EnricherResponse(BaseModel):
    customer_message: str
    query: str
    recipient: str
    session_context: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None
"""

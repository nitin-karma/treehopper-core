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

# enricher_c5 AGENT_YAML (FIXED)
inputs:
  - name: text
    type: string

  - name: emails
    type: array

  - name: metadata
    type: object

  # Optional passthroughs (NO sources)
  - name: intent
    type: string

  - name: urgency
    type: string

  - name: confidence
    type: number

outputs:
  - name: recipient
    type: string

  - name: channel
    type: string

  - name: subject
    type: string

  - name: priority
    type: string

  - name: query
    type: string   # 👈 PRODUCED HERE

  - name: session_context
    type: object



tags:
  - logic
  - normalization

version: '1.1'
"""

# ============================================================================
# HANDLER.PY
# ============================================================================

HANDLER_CODE = """from fastapi import Body
from typing import Dict, Any, List, Optional

from treehopper.treehopper import agent
from treehopper.agent_base import TreehopperAgentBase
from .schema import EnricherRequest, EnricherResponse


class ContextEnricherAgent(TreehopperAgentBase):
    async def run(self, request: EnricherRequest) -> EnricherResponse:
        await self.check_cancel()
        provider = (
            request.metadata.get("provider", "openai")
            if request.metadata else "openai"
        )

        try:
            context: Dict[str, Any] = {{}}
            final_message = ""
            final_recipient = ""

            # 📧 Email source
            if request.emails:
                first = request.emails[0]
                final_message = first.get("body") or first.get("text", "")
                final_recipient = first.get("from") or first.get("sender_email", "unknown")

                context.update({{
                    "source": "email",
                    "email_count": len(request.emails),
                    "subject": first.get("subject")
                }})

            # 💬 Direct text / CLI
            elif request.text:
                final_message = request.text
                final_recipient = "cli_user"
                context["source"] = "direct_text"

            # 🧩 Metadata merge
            if request.metadata:
                context.update(request.metadata)

            # 🧠 Normalize optional signals
            intent = request.intent or "general_query"
            urgency = request.urgency or "medium"
            confidence = request.confidence or 0.5

            context.update({{
                "intent": intent,
                "urgency": urgency,
                "confidence": confidence
            }})

            # 🔍 Search query heuristic
            query = " ".join(final_message.split()[:10])

            channel = request.metadata.get("channel", "email") if request.metadata else "email"
            subject = request.metadata.get("subject", "Support Response") if request.metadata else "Support Response"
            priority = request.metadata.get("priority", "medium") if request.metadata else "medium"

            return EnricherResponse(
                text=final_message,
                provider=provider,
                customer_message=final_message,
                query=query,
                recipient=final_recipient,

                # 👇 FLATTENED
                channel=channel,
                subject=subject,
                priority=priority,

                # 👇 still allowed for debugging / memory
                session_context=context,

                success=True
            )


        except Exception as e:
            return EnricherResponse(
                text="",
                provider="",
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
    return (await agent_instance.run(payload)).dict()
"""


# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class EnricherRequest(BaseModel):
    text: Optional[str] = None
    emails: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    intent: Optional[str] = None
    urgency: Optional[str] = None
    confidence: Optional[float] = None


class EnricherResponse(BaseModel):
    text: str
    provider: str
    customer_message: str
    query: str
    recipient: str
    session_context: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None
"""

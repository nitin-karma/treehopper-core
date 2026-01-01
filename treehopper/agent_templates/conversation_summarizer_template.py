"""
Template: Conversation Summarizer
Category: Memory
Description: Summarize long conversations into compact memory entries
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "conversation_summarizer",
    "version": "1.0.0",
    "category": "memory",
    "description": (
        "Summarizes conversation history into compact, durable memory. "
        "Used to control context length and improve long-term recall."
    ),
    "author": "TreehopperAI",
    "tags": ["conversation", "summary", "memory", "llm"],
    "dependencies": [],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Summarize conversation history
inputs:
  - name: conversation
    type: array
outputs:
  - name: summary
    type: string
version: "1.0"
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import ConversationSummaryRequest, ConversationSummaryResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class ConversationSummarizerAgent(TreehopperAgentBase):
    async def run(self, request: ConversationSummaryRequest) -> ConversationSummaryResponse:
        await self.check_cancel()

        convo = request.conversation or []
        if not convo:
            return ConversationSummaryResponse(summary="", success=True)

        # Deterministic, LLM-free baseline summarization
        lines = []
        for msg in convo[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(role + ": " + content)

        summary = " | ".join(lines)

        return ConversationSummaryResponse(
            summary=summary[:1000],
            success=True,
        )


@agent("{agent_name}", method="POST", goal="Summarize conversation into memory")
async def handle(payload: ConversationSummaryRequest = Body(...)):
    agent = ConversationSummarizerAgent()
    return (await agent.run(payload)).dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class ConversationSummaryRequest(BaseModel):
    conversation: List[Dict[str, Any]]


class ConversationSummaryResponse(BaseModel):
    summary: str = ""
    success: bool = True
    error: Optional[str] = None
"""

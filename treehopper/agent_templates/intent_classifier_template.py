"""
Template: Intent Classifier
Category: AI Intelligence
Description: Classify customer message intent using LLM for routing
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "intent_classifier",
    "version": "1.1.2",
    "category": "ai_intelligence",
    "description": "LLM-powered intent classifier with routing-safe outputs",
    "author": "TreehopperAI",
    "tags": ["ai", "llm", "classification", "intent"],
    "dependencies": ["treehopper_llm"],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Classify customer message intent and prepare downstream inputs
inputs:
  - name: text
    type: string
  - name: categories
    type: array
  - name: provider
    type: string
outputs:
  - name: intent
    type: string
  - name: confidence
    type: number
  - name: category
    type: string
  - name: sentiment
    type: string
  - name: urgency
    type: string
  - name: query
    type: string
  - name: customer_message
    type: string
  - name: suggested_action
    type: string
tags:
  - ai
  - classification
version: '1.1'
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """import json
from fastapi import Body
from typing import List

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.treehopper_llm import call_llm

from .schema import IntentClassifierRequest, IntentClassifierResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class IntentClassifierAgent(TreehopperAgentBase):
    DEFAULT_CATEGORIES = [
        "bug_report",
        "technical_support",
        "account_issue",
        "billing_question",
        "refund_request",
        "feature_request",
        "general_inquiry"
    ]

    def _build_prompt(self, text: str, categories: List[str]) -> str:
        cats = "\\n".join("- " + c for c in categories)

        return (
            "You are a customer support intent classifier.\\n\\n"
            "MESSAGE:\\n"
            + text
            + "\\n\\nCATEGORIES:\\n"
            + cats
            + "\\n\\nReturn ONLY valid JSON:\\n"
            + "{{\\n"
            + '  "intent": "...",\\n'
            + '  "confidence": 0.0,\\n'
            + '  "category": "...",\\n'
            + '  "sentiment": "positive|neutral|negative",\\n'
            + '  "urgency": "low|medium|high|critical",\\n'
            + '  "suggested_action": "..."\\n'
            + "}}\\n"
        )

    async def run(self, request: IntentClassifierRequest) -> IntentClassifierResponse:
        await self.check_cancel()

        text = (request.text or "").strip() or "General support request"
        categories = request.categories or self.DEFAULT_CATEGORIES
        provider = request.provider or "openai"

        customer_message = text
        query = " ".join(text.split()[:12])

        try:
            prompt = self._build_prompt(text, categories)

            llm_response = await call_llm(
                prompt=prompt,
                provider=provider,
                timeout=15
            )

            data = json.loads(llm_response.get("message", "{{}}"))

            return IntentClassifierResponse(
                intent=data.get("intent", "general_inquiry"),
                confidence=float(data.get("confidence", 0.5)),
                category=data.get("category", "general"),
                sentiment=data.get("sentiment", "neutral"),
                urgency=data.get("urgency", "medium"),
                suggested_action=data.get("suggested_action", "respond"),
                query=query,
                customer_message=customer_message,
                success=True
            )

        except Exception as e:
            return IntentClassifierResponse(
                intent="general_inquiry",
                confidence=0.3,
                category="general",
                sentiment="neutral",
                urgency="medium",
                suggested_action="respond",
                query=query,
                customer_message=customer_message,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Classify intent for routing")
async def handle(payload: IntentClassifierRequest = Body(...)):
    agent = IntentClassifierAgent()
    return (await agent.run(payload)).dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List


class IntentClassifierRequest(BaseModel):
    text: str = Field(..., min_length=1)
    categories: Optional[List[str]] = None
    provider: Optional[str] = Field("openai")


class IntentClassifierResponse(BaseModel):
    intent: str
    confidence: float = Field(ge=0, le=1)
    category: str
    sentiment: str
    urgency: str
    query: str
    customer_message: str
    suggested_action: str
    success: bool = True
    error: Optional[str] = None
"""

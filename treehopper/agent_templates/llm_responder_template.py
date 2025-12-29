"""
Template: LLM Responder
Category: AI Intelligence
Description: Generate personalized customer responses using LLM

Use Cases:
  - Automated support replies
  - FAQ answering
  - Contextual help generation
"""

TEMPLATE_INFO = {
    "name": "llm_responder",
    "version": "1.0.0",
    "category": "ai_intelligence",
    "description": "Context-aware response generation with LLM",
    "author": "TreehopperAI",
    "tags": ["ai", "llm", "response", "support"],
    "dependencies": ["treehopper_llm"],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Generate customer support responses using LLM
inputs:
  - name: customer_message
    type: string
    description: Customer message text (optional)
  - name: knowledge_articles
    type: array
    description: Retrieved knowledge base articles
  - name: tone
    type: string
    description: Response tone
  - name: provider
    type: string
    description: LLM provider
outputs:
  - name: response
    type: string
    description: Generated response text
  - name: confidence
    type: number
    description: Response quality confidence
  - name: needs_human
    type: boolean
    description: Whether human review is recommended
tags:
  - ai
  - llm
  - response
version: '1.1'
"""


HANDLER_CODE = """import json
from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.treehopper_llm import call_llm

from .schema import LLMResponderRequest, LLMResponderResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class LLMResponderAgent(TreehopperAgentBase):
    async def run(self, request: LLMResponderRequest) -> LLMResponderResponse:
        await self.check_cancel()

        # ---------- SAFE NORMALIZATION ----------
        customer_message = request.customer_message
        if not customer_message:
            if request.knowledge_articles:
                customer_message = "Please provide help based on the information below."
            else:
                customer_message = "Customer needs general assistance."

        tone = request.tone or "professional"
        provider = request.provider or "openai"

        knowledge_text = ""
        if request.knowledge_articles:
            for art in request.knowledge_articles[:3]:
                knowledge_text += "- {{title}}: {{content}}\\n".format(
                    title=art.get("title", ""),
                    content=art.get("content", "")
                )

        prompt = f\"\"\"You are a customer support agent.

TONE: {{tone}}

CUSTOMER MESSAGE:
{{customer_message}}

KNOWLEDGE BASE:
{{knowledge_text}}

TASK:
Write a clear, helpful customer support response.

Respond in plain text.
\"\"\"

        try:
            llm_response = await call_llm(
                prompt=prompt,
                provider=provider,
                timeout=20
            )

            message = llm_response.get("message", "").strip()
            if not message:
                raise ValueError("Empty LLM response")

            return LLMResponderResponse(
                response=message,
                confidence=0.6,
                needs_human=False
            )

        except Exception as e:
            return LLMResponderResponse(
                response="Thanks for contacting support. Our team will assist you shortly.",
                confidence=0.2,
                needs_human=True,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Generate customer support response using LLM")
async def handle(payload: LLMResponderRequest = Body(...)):
    agent_instance = LLMResponderAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""


SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class LLMResponderRequest(BaseModel):
    customer_message: Optional[str] = Field(
        None, description="Customer message"
    )
    knowledge_articles: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list
    )
    tone: Optional[str] = Field(
        "professional", description="Response tone"
    )
    provider: Optional[str] = Field(
        "openai", description="LLM provider"
    )


class LLMResponderResponse(BaseModel):
    response: str
    confidence: float = Field(0.5, ge=0, le=1)
    needs_human: bool = False
    success: bool = True
    error: Optional[str] = None
"""

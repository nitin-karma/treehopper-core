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
    description: Customer's message/question
  - name: context
    type: object
    description: Additional context (customer info, history)
  - name: knowledge_articles
    type: array
    description: Relevant knowledge base articles
  - name: tone
    type: string
    description: Response tone (professional/friendly/empathetic/concise)
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
version: '1.0'
"""

HANDLER_CODE = """import asyncio
import json
from fastapi import Body
from typing import Dict, Any

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.treehopper_llm import call_llm

from .schema import LLMResponderRequest, LLMResponderResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class LLMResponderAgent(TreehopperAgentBase):
    '''LLM-powered response generator'''

    TONE_INSTRUCTIONS = {{
        "professional": "Be professional, clear, and respectful.",
        "friendly": "Be warm, approachable, and conversational.",
        "empathetic": "Show understanding and empathy.",
        "concise": "Be brief and to-the-point."
    }}

    def _build_response_prompt(self, customer_message, context, knowledge_articles, tone, max_length):
        context_str = ""
        if context:
            items = [f"- {{k}}: {{v}}" for k, v in context.items() if v]
            if items:
                context_str = "CONTEXT:\\n" + "\\n".join(items) + "\\n\\n"

        knowledge_str = ""
        if knowledge_articles:
            kb_items = []
            for i, article in enumerate(knowledge_articles[:3], 1):
                kb_items.append(f"Article {{i}}: {{article.get('title', '')}}\\n{{article.get('content', '')}}")
            knowledge_str = "KNOWLEDGE:\\n" + "\\n".join(kb_items) + "\\n\\n"

        tone_instruction = self.TONE_INSTRUCTIONS.get(tone, self.TONE_INSTRUCTIONS["professional"])

        prompt = "You are a customer support agent.\\n\\n"
        prompt += context_str
        prompt += knowledge_str
        prompt += "CUSTOMER MESSAGE:\\n"
        prompt += customer_message
        prompt += "\\n\\nTASK: Generate a helpful response.\\n"
        prompt += f"TONE: {{tone_instruction}}\\n"
        prompt += f"MAX LENGTH: {{max_length}} words\\n\\n"
        prompt += "Respond with ONLY valid JSON (no markdown):\\n"
        prompt += "{{\\n"
        prompt += '  "response": "<your_response>",\\n'
        prompt += '  "confidence": <0.0 to 1.0>,\\n'
        prompt += '  "needs_human": <true or false>\\n'
        prompt += "}}\\n\\n"
        prompt += "JSON response:"

        return prompt

    def _parse_llm_response(self, llm_response):
        message = llm_response.get("message", "")
        try:
            message = message.strip()
            if message.startswith("```"):
                lines = message.split("\\n")
                message = "\\n".join([l for l in lines if not l.strip().startswith("```")])
            result = json.loads(message)
            result.setdefault("confidence", 0.5)
            result.setdefault("needs_human", False)
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            return result
        except:
            return {{
                "response": message or "I apologize, please contact support.",
                "confidence": 0.3,
                "needs_human": True
            }}

    async def run(self, request: LLMResponderRequest) -> LLMResponderResponse:
        await self.check_cancel()

        try:
            prompt = self._build_response_prompt(
                request.customer_message,
                request.context or {{}},
                request.knowledge_articles or [],
                request.tone,
                request.max_length
            )

            await self.check_cancel()

            llm_response = await call_llm(prompt=prompt, provider=request.provider, max_retries=2, timeout=20.0)

            if "error" in llm_response:
                return LLMResponderResponse(
                    response="We apologize for the inconvenience. Please contact support.",
                    confidence=0.0,
                    needs_human=True,
                    success=False,
                    error=llm_response["error"]
                )

            parsed = self._parse_llm_response(llm_response)

            response_text = parsed["response"]
            if request.include_signature:
                response_text += "\\n\\nBest regards,\\nCustomer Support"

            return LLMResponderResponse(
                response=response_text,
                confidence=parsed["confidence"],
                needs_human=parsed["needs_human"],
                used_knowledge=bool(request.knowledge_articles),
                success=True
            )
        except Exception as e:
            return LLMResponderResponse(
                response="We apologize. Please contact support@example.com.",
                confidence=0.0,
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
    customer_message: str = Field(..., description="Customer's message")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    knowledge_articles: Optional[List[Dict]] = Field(default_factory=list)
    tone: str = Field("professional", description="Response tone")
    max_length: int = Field(200, ge=50, le=500)
    include_signature: bool = Field(True)
    provider: str = Field("openai")


class LLMResponderResponse(BaseModel):
    response: str
    confidence: float = Field(..., ge=0, le=1)
    needs_human: bool = False
    used_knowledge: bool = False
    success: bool = True
    error: Optional[str] = None
"""

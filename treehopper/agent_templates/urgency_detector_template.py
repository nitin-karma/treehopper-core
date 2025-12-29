"""
Template: Urgency Detector
Category: AI Intelligence
Description: Detect urgency level of customer message

Use Cases:
  - Priority routing
  - SLA enforcement
  - Escalation triggers
"""

TEMPLATE_INFO = {
    "name": "urgency_detector",
    "version": "1.0.0",
    "category": "ai_intelligence",
    "description": "LLM-powered urgency detection",
    "author": "TreehopperAI",
    "tags": ["ai", "urgency", "priority", "routing"],
    "dependencies": ["treehopper_llm"],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Detect urgency level of message
inputs:
  - name: text
    type: string
    description: Message text to analyze
    source: request
  - name: provider
    type: string
    description: LLM provider
    source: request
outputs:
  - name: urgency
    type: string
    description: Urgency level (low/medium/high/critical)
  - name: confidence
    type: number
    description: Detection confidence 0-1
  - name: reasoning
    type: string
    description: Why this urgency level
  - name: requires_immediate_action
    type: boolean
    description: Whether immediate action needed
tags:
  - urgency
  - priority
  - routing
version: '1.0'
"""

HANDLER_CODE = """import asyncio
from fastapi import Body
from typing import Dict, Any

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.treehopper_llm import call_llm

from .schema import UrgencyDetectorRequest, UrgencyDetectorResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class UrgencyDetectorAgent(TreehopperAgentBase):
    '''Urgency detection using LLM + keywords'''

    CRITICAL_KEYWORDS = [
        "emergency", "critical", "urgent", "asap", "immediately",
        "broken", "down", "not working", "production", "revenue",
        "security", "breach", "hack", "crash", "outage"
    ]

    HIGH_KEYWORDS = [
        "important", "soon", "quickly", "needed", "problem",
        "issue", "error", "failed", "can't", "unable"
    ]

    def _keyword_score(self, text: str) -> tuple:
        text_lower = text.lower()

        critical_matches = sum(1 for kw in self.CRITICAL_KEYWORDS if kw in text_lower)
        high_matches = sum(1 for kw in self.HIGH_KEYWORDS if kw in text_lower)

        if critical_matches >= 2:
            return "critical", 0.9
        elif critical_matches == 1:
            return "high", 0.8
        elif high_matches >= 2:
            return "high", 0.7
        elif high_matches == 1:
            return "medium", 0.6
        else:
            return "low", 0.5

    async def run(self, request: UrgencyDetectorRequest) -> UrgencyDetectorResponse:
        await self.check_cancel()

        try:
            # Quick keyword scan
            keyword_urgency, keyword_conf = self._keyword_score(request.text)

            # LLM analysis for nuance
            prompt = f'''Analyze urgency (low/medium/high/critical):

Message: {request.text}

Consider:
- Customer emotion (calm vs frustrated vs angry)
- Business impact (minor inconvenience vs revenue loss)
- Time sensitivity (can wait vs needs immediate action)
- Safety/security concerns

Respond with JSON:
{{
  "urgency": "low|medium|high|critical",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "requires_immediate_action": true|false
}}
'''

            await self.check_cancel()

            llm_result = await call_llm(
                prompt=prompt,
                provider=request.provider,
                max_retries=2,
                timeout=10.0
            )

            if "error" in llm_result:
                # Fallback to keyword scoring
                return UrgencyDetectorResponse(
                    urgency=keyword_urgency,
                    confidence=keyword_conf,
                    reasoning="LLM unavailable, using keyword analysis",
                    requires_immediate_action=(keyword_urgency in ["critical", "high"]),
                    success=True
                )

            # Parse LLM response
            import json
            message = llm_result.get("message", "").strip()
            if message.startswith("```"):
                lines = message.split("\\n")
                message = "\\n".join([l for l in lines if not l.strip().startswith("```")])

            result = json.loads(message)

            return UrgencyDetectorResponse(
                urgency=result.get("urgency", "medium"),
                confidence=float(result.get("confidence", 0.5)),
                reasoning=result.get("reasoning", ""),
                requires_immediate_action=result.get("requires_immediate_action", False),
                success=True
            )

        except Exception as e:
            return UrgencyDetectorResponse(
                urgency="medium",
                confidence=0.3,
                reasoning=f"Error: {str(e)}",
                requires_immediate_action=False,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Detect message urgency level")
async def handle(payload: UrgencyDetectorRequest = Body(...)):
    agent_instance = UrgencyDetectorAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional


class UrgencyDetectorRequest(BaseModel):
    '''Input schema for urgency detector'''
    text: str = Field(..., description="Message text", min_length=1)
    provider: str = Field("openai", description="LLM provider")


class UrgencyDetectorResponse(BaseModel):
    '''Output schema for urgency detector'''
    urgency: str = Field(..., description="Urgency level")
    confidence: float = Field(..., description="Confidence 0-1", ge=0, le=1)
    reasoning: str = Field(..., description="Why this urgency")
    requires_immediate_action: bool = Field(False)
    success: bool = Field(True)
    error: Optional[str] = None
"""

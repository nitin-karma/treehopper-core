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

HANDLER_CODE = """from fastapi import Body
import json

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.treehopper_llm import call_llm


from .schema import UrgencyDetectorRequest, UrgencyDetectorResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class UrgencyDetectorAgent(TreehopperAgentBase):
    CRITICAL_KEYWORDS = [
        "emergency", "critical", "urgent", "asap", "immediately",
        "broken", "down", "not working", "production", "revenue",
        "security", "breach", "hack", "crash", "outage"
    ]

    HIGH_KEYWORDS = [
        "important", "soon", "quickly", "needed", "problem",
        "issue", "error", "failed", "can't", "unable"
    ]

    def _keyword_score(self, text):
        t = text.lower()
        critical = sum(1 for k in self.CRITICAL_KEYWORDS if k in t)
        high = sum(1 for k in self.HIGH_KEYWORDS if k in t)

        if critical >= 2:
            return "critical", 0.9
        if critical == 1:
            return "high", 0.8
        if high >= 2:
            return "high", 0.7
        if high == 1:
            return "medium", 0.6
        return "low", 0.5

    async def run(self, request: UrgencyDetectorRequest):
        await self.check_cancel()

        text = request.text
        provider = request.provider or "openai"

        kw_urgency, kw_conf = self._keyword_score(text)

        prompt = (
            "Analyze urgency (low/medium/high/critical).\\n\\n"
            "Message:\\n"
            + text
            + "\\n\\nReturn ONLY JSON:\\n"
            + '{{ "urgency": "low|medium|high|critical", '
            + '"confidence": 0.0, '
            + '"reasoning": "brief explanation", '
            + '"requires_immediate_action": true }}'
        )

        llm_result = await call_llm(
            prompt=prompt,
            provider=provider,
            timeout=10,
            max_retries=2
        )

        if "error" in llm_result:
            return UrgencyDetectorResponse(
                urgency=kw_urgency,
                confidence=kw_conf,
                reasoning="Keyword-based fallback",
                requires_immediate_action=(kw_urgency in ["high", "critical"]),
                success=True
            )

        raw = llm_result.get("message")

        if not raw or not isinstance(raw, str):
            # Fallback to keyword analysis
            return UrgencyDetectorResponse(
                urgency=kw_urgency,
                confidence=kw_conf,
                reasoning="Empty LLM response, keyword fallback",
                requires_immediate_action=(kw_urgency in ["high", "critical"]),
                success=True
            )
        raw = raw.strip()
        # Remove markdown fences if present
        if raw.startswith("```"):
            raw = "\\n".join(
                line for line in raw.splitlines()
                if not line.strip().startswith("```")
            ).strip()

        try:
            data = json.loads(raw)
        except Exception:
            return UrgencyDetectorResponse(
                urgency=kw_urgency,
                confidence=kw_conf,
                reasoning="Invalid JSON from LLM, keyword fallback",
                requires_immediate_action=(kw_urgency in ["high", "critical"]),
                success=True
            )
        return UrgencyDetectorResponse(
            urgency=data.get("urgency", kw_urgency),
            confidence=float(data.get("confidence", kw_conf)),
            reasoning=data.get("reasoning", ""),
            requires_immediate_action=data.get("requires_immediate_action", False),
            success=True
        )


@agent("{agent_name}", method="POST", goal="Detect urgency level")
async def handle(payload: UrgencyDetectorRequest = Body(...)):
    agent = UrgencyDetectorAgent()
    return (await agent.run(payload)).dict()
"""


SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional


class UrgencyDetectorRequest(BaseModel):
    '''Input schema for urgency detector'''
    text: str = Field(..., description="Message text", min_length=1)
    provider: Optional[str] = Field(None, description="LLM provider")


class UrgencyDetectorResponse(BaseModel):
    '''Output schema for urgency detector'''
    urgency: str = Field(..., description="Urgency level")
    confidence: float = Field(..., description="Confidence 0-1", ge=0, le=1)
    reasoning: str = Field(..., description="Why this urgency")
    requires_immediate_action: bool = Field(False)
    success: bool = Field(True)
    error: Optional[str] = None
"""

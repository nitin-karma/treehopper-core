"""
Template: Sentiment Analyzer
Category: Analysis
Description: Detects sentiment from input text
"""

TEMPLATE_INFO = {
    "name": "sentiment_analyzer",
    "version": "1.0.0",
    "category": "analysis",
    "description": "Lightweight sentiment detection (positive / neutral / negative)",
    "author": "TreehopperAI",
    "tags": ["sentiment", "analysis", "confidence"],
    "dependencies": [],
}

AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Sentiment analysis agent

inputs:
  - name: text
    type: string
    description: Input message text

outputs:
  - name: sentiment
    type: string
    description: positive | neutral | negative

  - name: confidence
    type: number
    description: Confidence score (0–1)

version: '1.0'
"""

HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent
from treehopper.agent_base import TreehopperAgentBase
from .schema import SentimentRequest, SentimentResponse


class SentimentAnalyzerAgent(TreehopperAgentBase):
    async def run(self, request: SentimentRequest) -> SentimentResponse:
        await self.check_cancel()

        text = (request.text or "").lower()

        negative_words = [
            "angry", "bad", "broken", "fail", "issue",
            "problem", "error", "complaint", "urgent"
        ]

        positive_words = [
            "thanks", "thank you", "great", "good",
            "awesome", "excellent", "love"
        ]

        score = 0

        for w in negative_words:
            if w in text:
                score -= 1

        for w in positive_words:
            if w in text:
                score += 1

        if score < 0:
            return SentimentResponse(
                sentiment="negative",
                confidence=min(0.9, 0.6 + abs(score) * 0.1)
            )

        if score > 0:
            return SentimentResponse(
                sentiment="positive",
                confidence=min(0.9, 0.6 + score * 0.1)
            )

        return SentimentResponse(
            sentiment="neutral",
            confidence=0.6
        )


@agent("{agent_name}", method="POST", goal="Analyze sentiment")
async def handle(payload: SentimentRequest = Body(...)):
    agent_instance = SentimentAnalyzerAgent()
    return (await agent_instance.run(payload)).dict()
"""

SCHEMA_CODE = """from pydantic import BaseModel, Field


class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=1)


class SentimentResponse(BaseModel):
    sentiment: str
    confidence: float
"""

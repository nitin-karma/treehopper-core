"""
Template: Intent Classifier
Category: AI Intelligence
Description: Classify customer message intent using LLM for routing

Use Cases:
  - Support ticket routing
  - Email categorization
  - Chat intent detection
  - Priority classification
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "intent_classifier",
    "version": "1.0.0",
    "category": "ai_intelligence",
    "description": "LLM-powered intent classification with confidence scoring",
    "author": "TreehopperAI",
    "tags": ["ai", "llm", "classification", "intent", "nlp"],
    "dependencies": ["treehopper_llm"],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Classify customer message intent using LLM
inputs:
  - name: text
    type: string
    description: Text to classify
  - name: categories
    type: array
    description: Optional custom intent categories
  - name: include_sentiment
    type: boolean
    description: Include sentiment analysis
  - name: provider
    type: string
    description: LLM provider (openai, gemini, perplexity)
outputs:
  - name: intent
    type: string
    description: Detected intent category
  - name: confidence
    type: number
    description: Confidence score 0-1
  - name: category
    type: string
    description: Broader category grouping
  - name: sentiment
    type: string
    description: Sentiment (positive/neutral/negative)
  - name: urgency
    type: string
    description: Urgency level (low/medium/high/critical)
  - name: suggested_action
    type: string
    description: Recommended next step
tags:
  - ai
  - classification
  - llm
  - intent
version: '1.0'
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """import asyncio
import json
from fastapi import Body
from typing import Optional, List, Dict, Any

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.treehopper_llm import call_llm

from .schema import IntentClassifierRequest, IntentClassifierResponse

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class IntentClassifierAgent(TreehopperAgentBase):
    '''Intent classification using LLM'''

    DEFAULT_CATEGORIES = [
        "refund_request",
        "bug_report",
        "feature_request",
        "billing_question",
        "technical_support",
        "account_issue",
        "product_question",
        "complaint",
        "praise",
        "general_inquiry"
    ]

    def _build_classification_prompt(
        self,
        text: str,
        categories: List[str],
        include_sentiment: bool
    ) -> str:
        '''Build LLM prompt for classification'''

        categories_str = "\\n".join([f"  - {{cat}}" for cat in categories])

        sentiment_instruction = ""
        if include_sentiment:
            sentiment_instruction = '\\n- sentiment: One of [positive, neutral, negative]'

        prompt = "You are an expert customer support intent classifier.\\n\\n"
        prompt += "Analyze this customer message and classify it into the most appropriate category.\\n\\n"
        prompt += "MESSAGE:\\n"
        prompt += text
        prompt += "\\n\\nAVAILABLE CATEGORIES:\\n"
        prompt += categories_str
        prompt += "\\n\\nRespond with ONLY a valid JSON object (no markdown, no code blocks):\\n"
        prompt += "{{\\n"
        prompt += '  "intent": "<most_specific_category>",\\n'
        prompt += '  "confidence": <0.0 to 1.0>,\\n'
        prompt += '  "category": "<broader_category>",\\n'
        prompt += '  "subcategory": "<specific_detail or null>",'
        prompt += sentiment_instruction
        prompt += '\\n  "urgency": "<low|medium|high|critical>",\\n'
        prompt += '  "suggested_action": "<recommended_next_step>",\\n'
        prompt += '  "reasoning": "<brief_explanation>"\\n'
        prompt += "}}\\n\\n"
        prompt += "GUIDELINES:\\n"
        prompt += "- Choose the MOST SPECIFIC category that fits\\n"
        prompt += "- Confidence reflects certainty (0.0 = unsure, 1.0 = certain)\\n"
        prompt += "- Urgency based on customer emotion and issue severity\\n"
        prompt += "- Be decisive - always pick one category\\n"
        prompt += "- Keep reasoning under 50 words\\n\\n"
        prompt += "JSON response:"

        return prompt

    def _parse_llm_response(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        '''Parse and validate LLM response'''

        message = llm_response.get("message", "")

        try:
            # Clean up response
            message = message.strip()
            if message.startswith("```"):
                lines = message.split("\\n")
                message = "\\n".join([
                    line for line in lines
                    if not line.strip().startswith("```")
                ])

            result = json.loads(message)

            # Validate required fields
            required = ["intent", "confidence", "category", "urgency", "suggested_action", "reasoning"]
            for field in required:
                if field not in result:
                    raise ValueError(f"Missing required field: {{field}}")

            # Ensure confidence is valid
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

            return result

        except (json.JSONDecodeError, ValueError) as e:
            return {{
                "intent": "general_inquiry",
                "confidence": 0.3,
                "category": "general",
                "subcategory": None,
                "sentiment": "neutral",
                "urgency": "medium",
                "suggested_action": "route_to_general_support",
                "reasoning": f"Failed to parse LLM response: {{str(e)}}"
            }}

    async def run(self, request: IntentClassifierRequest) -> IntentClassifierResponse:
        '''Classify customer message intent'''
        await self.check_cancel()

        try:
            categories = request.categories or self.DEFAULT_CATEGORIES

            # Build prompt
            prompt = self._build_classification_prompt(
                text=request.text,
                categories=categories,
                include_sentiment=request.include_sentiment
            )

            await self.check_cancel()

            # Call LLM
            llm_response = await call_llm(
                prompt=prompt,
                provider=request.provider,
                max_retries=2,
                timeout=15.0
            )

            if "error" in llm_response:
                return IntentClassifierResponse(
                    intent="unknown",
                    confidence=0.0,
                    category="error",
                    urgency="medium",
                    suggested_action="manual_review",
                    reasoning=f"LLM error: {{llm_response['error']}}",
                    success=False,
                    error=llm_response["error"]
                )

            # Parse response
            classification = self._parse_llm_response(llm_response)

            await self.check_cancel()

            return IntentClassifierResponse(
                intent=classification["intent"],
                confidence=classification["confidence"],
                category=classification["category"],
                subcategory=classification.get("subcategory"),
                sentiment=classification.get("sentiment"),
                urgency=classification["urgency"],
                suggested_action=classification["suggested_action"],
                reasoning=classification["reasoning"],
                success=True
            )

        except Exception as e:
            return IntentClassifierResponse(
                intent="error",
                confidence=0.0,
                category="error",
                urgency="medium",
                suggested_action="manual_review",
                reasoning=f"Classification failed: {{str(e)}}",
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Classify customer message intent using LLM")
async def handle(payload: IntentClassifierRequest = Body(...)):
    '''FastAPI handler for intent classification'''
    agent_instance = IntentClassifierAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List


class IntentClassifierRequest(BaseModel):
    '''Input schema for intent classifier'''
    text: str = Field(..., description="Text to classify", min_length=1)
    categories: Optional[List[str]] = Field(
        None,
        description="Custom intent categories (defaults to common support intents)"
    )
    include_sentiment: bool = Field(
        True,
        description="Include sentiment analysis"
    )
    provider: str = Field(
        "openai",
        description="LLM provider (openai, gemini, perplexity)"
    )


class IntentClassifierResponse(BaseModel):
    '''Output schema for intent classifier'''
    intent: str = Field(..., description="Detected intent")
    confidence: float = Field(..., description="Confidence score 0-1", ge=0, le=1)
    category: str = Field(..., description="Broader category")
    subcategory: Optional[str] = Field(None, description="Specific subcategory")
    sentiment: Optional[str] = Field(None, description="Sentiment (positive/neutral/negative)")
    urgency: str = Field(..., description="Urgency level (low/medium/high/critical)")
    suggested_action: str = Field(..., description="Recommended action")
    reasoning: str = Field(..., description="Classification reasoning")
    success: bool = Field(True, description="Operation success")
    error: Optional[str] = Field(None, description="Error message if failed")
"""

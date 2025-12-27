"""
Template: Knowledge Search
Category: Data Transformation
Description: Search knowledge base for relevant articles using semantic similarity

Use Cases:
  - FAQ retrieval
  - Documentation search
  - Policy lookup
  - Troubleshooting guide matching
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "knowledge_search",
    "version": "1.0.0",
    "category": "data_transformation",
    "description": "Search knowledge base with semantic similarity matching",
    "author": "TreehopperAI",
    "tags": ["search", "knowledge-base", "faq", "similarity"],
    "dependencies": [],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Search knowledge base for relevant articles
inputs:
  - name: query
    type: string
    description: Search query text
  - name: top_k
    type: integer
    description: Number of results to return
  - name: min_relevance
    type: number
    description: Minimum relevance threshold (0-1)
  - name: knowledge_base
    type: string
    description: Knowledge base name
outputs:
  - name: articles
    type: array
    description: Matching knowledge articles
  - name: count
    type: integer
    description: Number of results found
  - name: best_match_score
    type: number
    description: Highest relevance score
tags:
  - search
  - knowledge
  - faq
version: '1.0'
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """import asyncio
from fastapi import Body
from typing import Optional, List, Dict, Any

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase

from .schema import KnowledgeSearchRequest, KnowledgeSearchResponse, KnowledgeArticle

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class KnowledgeSearchAgent(TreehopperAgentBase):
    '''Knowledge base search with semantic similarity'''

    def __init__(self):
        super().__init__()
        self.knowledge_bases = self._load_knowledge_bases()

    def _load_knowledge_bases(self) -> Dict[str, List[Dict]]:
        '''Load knowledge bases (sample data for demo)'''

        return {{
            "default": [
                {{
                    "id": "kb001",
                    "title": "How to Reset Your Password",
                    "content": "To reset your password: 1) Go to login page 2) Click 'Forgot Password' 3) Enter your email 4) Check your inbox for reset link 5) Click link and set new password",
                    "category": "account",
                    "tags": ["password", "reset", "login", "account"],
                    "url": "https://help.example.com/reset-password"
                }},
                {{
                    "id": "kb002",
                    "title": "Refund Policy",
                    "content": "Our refund policy: Full refunds within 30 days of purchase. Items must be unused and in original packaging. Digital products are non-refundable after download. Contact support@example.com to initiate refund.",
                    "category": "billing",
                    "tags": ["refund", "return", "money-back", "billing"],
                    "url": "https://help.example.com/refund-policy"
                }},
                {{
                    "id": "kb003",
                    "title": "Troubleshooting Login Issues",
                    "content": "Can't log in? Try: 1) Clear browser cache 2) Try incognito mode 3) Disable extensions 4) Check Caps Lock 5) Reset password 6) Contact support",
                    "category": "technical",
                    "tags": ["login", "troubleshooting", "access", "technical"],
                    "url": "https://help.example.com/login-issues"
                }},
                {{
                    "id": "kb004",
                    "title": "How to Cancel Subscription",
                    "content": "To cancel: 1) Log in 2) Go to Settings > Billing 3) Click 'Manage Subscription' 4) Select 'Cancel' 5) Confirm. You'll retain access until end of billing period.",
                    "category": "billing",
                    "tags": ["cancel", "subscription", "billing"],
                    "url": "https://help.example.com/cancel"
                }},
                {{
                    "id": "kb005",
                    "title": "Shipping Information",
                    "content": "Standard (5-7 days) free over $50. Express (2-3 days) $15. International (10-14 days) varies. Track orders in your account.",
                    "category": "shipping",
                    "tags": ["shipping", "delivery", "tracking"],
                    "url": "https://help.example.com/shipping"
                }}
            ]
        }}

    def _calculate_relevance(self, query: str, article: Dict) -> float:
        '''Calculate relevance score (keyword matching)'''
        query_lower = query.lower()
        query_words = set(query_lower.split())

        searchable = " ".join([
            article.get("title", ""),
            article.get("content", ""),
            " ".join(article.get("tags", []))
        ]).lower()

        matches = sum(1 for word in query_words if word in searchable)

        if query_lower in article.get("title", "").lower():
            matches += 3

        if any(query_lower == tag.lower() for tag in article.get("tags", [])):
            matches += 2

        max_score = len(query_words) + 5
        score = min(1.0, matches / max_score) if max_score > 0 else 0.0

        return round(score, 3)

    async def run(self, request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
        '''Search knowledge base for relevant articles'''
        await self.check_cancel()

        try:
            kb_name = request.knowledge_base
            kb_articles = self.knowledge_bases.get(kb_name, [])

            if not kb_articles:
                return KnowledgeSearchResponse(
                    articles=[],
                    count=0,
                    best_match_score=0.0,
                    success=False,
                    error=f"Knowledge base '{{kb_name}}' not found"
                )

            scored_articles = []

            for article in kb_articles:
                await self.cancelable_sleep(0.01)

                relevance = self._calculate_relevance(request.query, article)

                if relevance >= request.min_relevance:
                    scored_articles.append({{
                        **article,
                        "relevance_score": relevance
                    }})

            scored_articles.sort(key=lambda x: x["relevance_score"], reverse=True)
            top_articles = scored_articles[:request.top_k]

            result_articles = []
            for article in top_articles:
                content = article["content"]
                if not request.include_content:
                    content = content[:200] + "..." if len(content) > 200 else content

                result_articles.append(KnowledgeArticle(
                    id=article["id"],
                    title=article["title"],
                    content=content,
                    category=article.get("category"),
                    tags=article.get("tags", []),
                    relevance_score=article["relevance_score"],
                    url=article.get("url")
                ))

            best_score = top_articles[0]["relevance_score"] if top_articles else 0.0

            return KnowledgeSearchResponse(
                articles=result_articles,
                count=len(result_articles),
                best_match_score=best_score,
                success=True
            )

        except Exception as e:
            return KnowledgeSearchResponse(
                articles=[],
                count=0,
                best_match_score=0.0,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Search knowledge base for relevant articles")
async def handle(payload: KnowledgeSearchRequest = Body(...)):
    '''FastAPI handler for knowledge search'''
    agent_instance = KnowledgeSearchAgent()
    result = await agent_instance.run(payload)
    return result.dict()
"""

# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel, Field
from typing import Optional, List


class KnowledgeArticle(BaseModel):
    '''Single knowledge article'''
    id: str
    title: str
    content: str
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    relevance_score: float
    url: Optional[str] = None


class KnowledgeSearchRequest(BaseModel):
    '''Input schema for knowledge search'''
    query: str = Field(..., description="Search query", min_length=1)
    top_k: int = Field(5, description="Number of results", ge=1, le=50)
    min_relevance: float = Field(0.3, description="Min relevance threshold", ge=0, le=1)
    knowledge_base: str = Field("default", description="Knowledge base name")
    include_content: bool = Field(True, description="Include full article content")


class KnowledgeSearchResponse(BaseModel):
    '''Output schema for knowledge search'''
    articles: List[KnowledgeArticle] = Field(default_factory=list)
    count: int = Field(0)
    best_match_score: float = Field(0.0)
    success: bool = Field(True)
    error: Optional[str] = None
"""

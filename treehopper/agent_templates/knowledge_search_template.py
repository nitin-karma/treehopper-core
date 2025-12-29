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
    description: Search query text (optional)
  - name: emails
    type: array
    description: Optional email objects to derive query from
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
  - name: knowledge_articles
    type: array
    description: Matching knowledge articles
  - name: count
    type: integer
  - name: best_match_score
    type: number
tags:
  - search
  - knowledge
  - faq
version: '1.0'
"""

# ============================================================================
# HANDLER.PY
# ============================================================================
HANDLER_CODE = """from pathlib import Path
import json
import asyncio
from fastapi import Body
from typing import Optional, List, Dict, Any

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.th_config import TH_ROOT
from .schema import KnowledgeSearchRequest, KnowledgeSearchResponse, KnowledgeArticle

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)


class KnowledgeSearchAgent(TreehopperAgentBase):
    '''Knowledge base search with semantic similarity'''

    def __init__(self):
        super().__init__()
        self.knowledge_bases = self._load_knowledge_bases()

    def _load_knowledge_bases(self) -> Dict[str, List[Dict[str, Any]]]:
        '''
        Primary: Load knowledge from Postgres (if configured)
        Secondary: Fallback to local synthetic_data/kb.json
        '''

        import os
        import json
        from pathlib import Path
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import SQLAlchemyError

        # ---------- 1. CHECK IF DB IS CONFIGURED ----------
        try:
            db_user = os.getenv("DB_USER", None)
            db_password = os.getenv("DB_PASSWORD", None)
            db_name = os.getenv("DB_NAME", None)

            if db_user and db_password and db_name:
                db_host = os.getenv("DB_HOST", "localhost")
                db_port = os.getenv("DB_PORT", "5432")

                db_url = f"postgresql://{{db_user}}:{{db_password}}@{{db_host}}:{{db_port}}/{{db_name}}"


                engine = create_engine(
                    db_url,
                    connect_args={{"connect_timeout": 2}},
                    pool_pre_ping=True
                )

                with engine.connect() as conn:
                    result = conn.execute(text(\"\"\"
                        SELECT id, title, content, category, tags, url
                        FROM knowledge_articles
                    \"\"\"))

                    articles = []
                    for row in result:
                        item = dict(row._mapping)

                        # Normalize tags
                        if isinstance(item.get("tags"), str):
                            item["tags"] = [t.strip() for t in item["tags"].split(",")]

                        articles.append(item)

                    print(f"[knowledge_search] ✅ Loaded {{len(articles)}} articles from Postgres")
                    return {{"default": articles}}

        except (SQLAlchemyError, Exception) as e:
            print(f"[knowledge_search] ⚠️ Postgres unavailable, falling back to JSON: {{e}}")

        # ---------- 2. FALLBACK TO LOCAL JSON ----------
        try:
            #agent_dir = Path(__file__).resolve().parent
            #kb_path = agent_dir.parent / "synthetic_data" / "kb.json"
            kb_path = TH_ROOT / "registry" / "shared" / agent_id / "files" / "kb.json"

            if not kb_path.exists():
                print(f"[knowledge_search] ❌ No KB found at {{kb_path}}")
                return {{"default": []}}

            with kb_path.open("r", encoding="utf-8") as f:
                kb_data = json.load(f)

            print(f"[knowledge_search] 📦 Loaded KB from {{kb_path}}")
            return {{"default": kb_data}} if isinstance(kb_data, list) else kb_data

        except Exception as e:
            print(f"[knowledge_search] ❌ Critical KB load failure: {{e}}")
            return {{"default": []}}


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
            # -------------------------------
            # Resolve inputs SAFELY
            # -------------------------------
            query = request.query
            if not query and request.emails:
                first = request.emails[0]
                query = first.get("body") if isinstance(first, dict) else getattr(first, "body", "")


            if not query or not query.strip():
                query = "general support request"

            top_k = request.top_k or 5
            min_relevance = request.min_relevance or 0.3

            knowledge_base = request.knowledge_base or "default"
            kb_articles = self.knowledge_bases.get(knowledge_base, [])

            if not kb_articles:
                return KnowledgeSearchResponse(
                    articles=[],
                    count=0,
                    best_match_score=0.0,
                    success=False,
                    error=f"Knowledge base '{{knowledge_base}}' not found"
                )

            scored_articles = []

            for article in kb_articles:
                await self.cancelable_sleep(0.01)

                relevance = self._calculate_relevance(query, article)

                if relevance >= min_relevance:
                    scored_articles.append({{
                        **article,
                        "relevance_score": relevance
                    }})

            scored_articles.sort(key=lambda x: x["relevance_score"], reverse=True)
            top_articles = scored_articles[:top_k]

            result_articles = []
            for article in top_articles:
                content = article.get("content", "")
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
                knowledge_articles=result_articles,
                count=len(result_articles),
                best_match_score=best_score,
                success=True
            )

        except Exception as e:
            return KnowledgeSearchResponse(
                knowledge_articles=[],
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
from typing import Optional, List, Dict, Any


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
    emails: Optional[List[Dict]] = None
    query: Optional[str] = None
    top_k: Optional[int] = None
    min_relevance: Optional[float] = None
    knowledge_base: Optional[str] = None


class KnowledgeSearchResponse(BaseModel):
    knowledge_articles: List[KnowledgeArticle] = Field(default_factory=list)
    count: int = 0
    best_match_score: float = 0.0
    success: bool = True
    error: Optional[str] = None

"""

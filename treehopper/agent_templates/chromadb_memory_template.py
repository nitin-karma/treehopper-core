"""
Template: ChromaDB Memory
Category: Memory
Description: Semantic memory using ChromaDB for recall, search, and caching
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "chromadb_memory",
    "version": "1.0.0",
    "category": "memory",
    "description": "Semantic memory using ChromaDB for recall, search, and caching",
    "author": "TreehopperAI",
    "tags": ["memory", "chromadb", "semantic", "cache"],
    "dependencies": ["chromadb"],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Semantic memory using ChromaDB
inputs:
  - name: mode
    type: string
    description: read | write | search

  - name: session_id
    type: string
    required: false

  - name: collection
    type: string
    default: default_memory

  - name: text
    type: string
    required: false

  - name: metadata
    type: object
    required: false

  - name: top_k
    type: number
    default: 3

outputs:
  - name: results
    type: array
  - name: hit
    type: boolean
  - name: confidence
    type: number
version: "1.0"
"""

# ============================================================================
# HANDLER.PY  ✅ FORMAT-SAFE
# ============================================================================
HANDLER_CODE = """from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.logging import get_logger

import chromadb
from chromadb.utils import embedding_functions

from .schema import ChromaMemoryRequest, ChromaMemoryResponse

logger = get_logger()

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

client = chromadb.Client()
embedding_fn = embedding_functions.DefaultEmbeddingFunction()


class ChromaMemoryAgent(TreehopperAgentBase):
    async def run(self, request: ChromaMemoryRequest) -> ChromaMemoryResponse:
        await self.check_cancel()

        collection_name = request.collection or "default_memory"
        mode = request.mode
        text = request.text
        metadata = request.metadata or dict()
        top_k = request.top_k or 3

        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn
        )

        try:
            if mode == "write":
                if not text:
                    return ChromaMemoryResponse(
                        results=[],
                        hit=False,
                        confidence=0.0,
                        success=False,
                        error="Missing text for write"
                    )

                collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    ids=[self.make_run_id()]
                )

                return ChromaMemoryResponse(
                    results=[],
                    hit=True,
                    confidence=1.0,
                    success=True
                )

            if mode == "search":
                if not text:
                    return ChromaMemoryResponse(
                        results=[],
                        hit=False,
                        confidence=0.0,
                        success=False,
                        error="Missing text for search"
                    )

                res = collection.query(
                    query_texts=[text],
                    n_results=top_k
                )

                docs = res.get("documents", [[]])[0]
                distances = res.get("distances", [[]])[0]

                hit = len(docs) > 0
                confidence = 1.0 - min(distances) if distances else 0.0

                return ChromaMemoryResponse(
                    results=docs,
                    hit=hit,
                    confidence=confidence,
                    success=True
                )

            return ChromaMemoryResponse(
                results=[],
                hit=False,
                confidence=0.0,
                success=False,
                error="Invalid mode"
            )

        except Exception as e:
            logger.exception("chromadb_memory failed")
            return ChromaMemoryResponse(
                results=[],
                hit=False,
                confidence=0.0,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Semantic memory using ChromaDB")
async def handle(payload: ChromaMemoryRequest = Body(...)):
    agent = ChromaMemoryAgent()
    return (await agent.run(payload)).dict()
"""


# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChromaMemoryRequest(BaseModel):
    mode: str
    session_id: Optional[str] = None
    collection: Optional[str] = None
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    top_k: Optional[int] = 3


class ChromaMemoryResponse(BaseModel):
    results: List[Dict[str, Any]] = []
    hit: bool = False
    confidence: float = 0.0
    success: bool = True
    error: Optional[str] = None
"""

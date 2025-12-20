import os
import asyncio
import json
from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from treehopper.treehopper_llm import call_llm

from .schema import ContentAnalyzerRequest

agent_name = "content_analyzer"
agent_id = get_agent_id(agent_name)


def _normalize_entities(raw_entities) -> list[str]:
    """
    Ensure key_entities is ALWAYS List[str]
    regardless of LLM or mock output shape.
    """
    normalized = []

    for e in raw_entities or []:
        if isinstance(e, str):
            normalized.append(e)
        elif isinstance(e, dict):
            # prefer "name", fallback to stringified dict
            normalized.append(str(e.get("name") or e))
        else:
            normalized.append(str(e))

    return normalized


@agent("content_analyzer", method="POST", goal="Analyze document content")
async def handle(payload: ContentAnalyzerRequest = Body(...)):
    run_id = get_run_id()

    print("[content_analyzer] READY")
    await th_sleep(0)

    # --------------------------------------------------
    # Cancellation pre-check
    # --------------------------------------------------
    if run_id and await is_run_cancelled(run_id):
        print("[content_analyzer] CANCEL detected before execution")
        raise asyncio.CancelledError()

    text = payload.extracted_text[:4000]
    provider = os.getenv("TH_LLM_PROVIDER", "openai")

    # ==================================================
    # 🧪 MOCK MODE (CI / TEST / NO LLM)
    # ==================================================
    if provider == "mock" or os.getenv("TH_TEST_MODE") == "1":
        print("[content_analyzer] MOCK MODE ENABLED")

        sentiment = (
            "negative"
            if any(k in text.lower() for k in ("terminate", "penalty", "breach"))
            else "positive"
        )

        return {
            "sentiment": sentiment,
            "key_entities": [
                "Client",
                "Service Provider",
                payload.file_name,
            ],
            "summary": f"Mock analysis for {payload.file_name}",
            "themes": ["contract", "agreement"],
            "file_name": payload.file_name,
            "page_count": payload.page_count,
        }

    # ==================================================
    # 🤖 REAL LLM MODE
    # ==================================================
    print("[content_analyzer] Calling LLM...")

    prompt = f"""
Analyze the following document text and provide:
1. Sentiment (positive / negative / neutral)
2. Key entities (names only)
3. Short summary
4. Main themes

Document: {payload.file_name}

Text:
{text}

Respond ONLY with valid JSON:
{{
  "sentiment": "...",
  "key_entities": ["..."],
  "summary": "...",
  "themes": ["..."]
}}
"""

    llm_result = await call_llm(
        prompt=prompt,
        provider=provider,
        max_retries=3,
        timeout=30.0,
    )

    if "error" in llm_result:
        raise RuntimeError(llm_result["error"])

    response_text = (
        llm_result["message"].replace("```json", "").replace("```", "").strip()
    )

    try:
        analysis = json.loads(response_text)
    except json.JSONDecodeError:
        analysis = {
            "sentiment": "neutral",
            "key_entities": [],
            "summary": response_text[:200],
            "themes": [],
        }

    return {
        "sentiment": analysis.get("sentiment", "neutral"),
        "key_entities": _normalize_entities(analysis.get("key_entities")),
        "summary": analysis.get("summary", ""),
        "themes": analysis.get("themes", []),
        "file_name": payload.file_name,
        "page_count": payload.page_count,
    }

import asyncio
import json
from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from treehopper.treehopper_llm import call_llm
from .schema import KeywordExtractorRequest

agent_name = "keyword_extractor"
agent_id = get_agent_id(agent_name)


@agent("keyword_extractor", method="POST", goal="Extract important keywords from text")
async def handle(payload: KeywordExtractorRequest = Body(...)):
    run_id = get_run_id()

    print("[keyword_extractor] READY")
    await th_sleep(0)

    # Pre-cancel check
    if run_id and await is_run_cancelled(run_id):
        print("[keyword_extractor] CANCEL detected before starting")
        raise asyncio.CancelledError()

    text = payload.extracted_text[:4000]  # truncate for LLM safety
    print(f"[keyword_extractor] Extracting keywords from {len(text)} characters")

    try:
        # Final cancel check before LLM call
        if run_id and await is_run_cancelled(run_id):
            print("[keyword_extractor] CANCEL detected before LLM call")
            raise asyncio.CancelledError()

        prompt = f"""
Extract the top 10 important keywords from the following text.
Return ONLY valid JSON in this format:

{{
  "keywords": ["word1", "word2", ...]
}}

Text:
{text}
"""

        print("[keyword_extractor] Calling LLM...")

        llm_result = await call_llm(
            prompt=prompt,
            provider="openai",
            max_retries=3,
            timeout=20.0,
        )

        if "error" in llm_result:
            raise Exception(f"LLM failed: {llm_result['error']}")

        response_text = llm_result["message"]
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            parsed = {"keywords": []}

        keywords = parsed.get("keywords", [])
        print(f"[keyword_extractor] Extracted {len(keywords)} keywords")

        return {"keywords": keywords}

    except asyncio.CancelledError:
        print("[keyword_extractor] CANCELLED during extraction")
        raise
    except Exception as e:
        print(f"[keyword_extractor] ERROR: {e}")
        raise

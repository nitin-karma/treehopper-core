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


@agent("content_analyzer", method="POST", goal="Analyze document content with AI")
async def handle(payload: ContentAnalyzerRequest = Body(...)):
    run_id = get_run_id()

    print("[content_analyzer] READY")
    await th_sleep(0)

    # Pre-check cancellation
    if run_id and await is_run_cancelled(run_id):
        print("[content_analyzer] CANCEL detected before starting")
        raise asyncio.CancelledError()

    print(f"[content_analyzer] Analyzing {len(payload.extracted_text)} characters")

    try:
        # Truncate text if too long (LLM context limits)
        text = payload.extracted_text[:4000]  # First 4000 chars

        # Check cancellation before expensive LLM call
        if run_id and await is_run_cancelled(run_id):
            print("[content_analyzer] CANCEL detected before LLM call")
            raise asyncio.CancelledError()

        # Build analysis prompt
        prompt = f"""Analyze the following document text and provide:

1. Sentiment (positive, negative, or neutral)
2. Key entities (names, organizations, locations) - list up to 5
3. A brief summary (2-3 sentences)
4. Main themes or topics - list up to 3

Document: {payload.file_name}

Text:
{text}

Respond ONLY with valid JSON in this format:
{{
  "sentiment": "positive|negative|neutral",
  "key_entities": ["entity1", "entity2", ...],
  "summary": "Brief summary here",
  "themes": ["theme1", "theme2", ...]
}}"""

        print("[content_analyzer] Calling LLM...")

        # Call LLM with retries
        llm_result = await call_llm(
            prompt=prompt,
            provider="openai",  # or "mock" for testing
            max_retries=3,
            timeout=30.0,
        )

        # Check for LLM errors
        if "error" in llm_result:
            raise Exception(f"LLM failed: {llm_result['error']}")

        # Parse LLM response
        response_text = llm_result["message"]

        # Clean markdown code fences if present
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        try:
            analysis = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            analysis = {
                "sentiment": "neutral",
                "key_entities": [],
                "summary": response_text[:200],
                "themes": [],
            }

        print(f"[content_analyzer] Analysis complete: {analysis.get('sentiment')}")

        return {
            "sentiment": analysis.get("sentiment", "neutral"),
            "key_entities": analysis.get("key_entities", []),
            "summary": analysis.get("summary", ""),
            "themes": analysis.get("themes", []),
        }

    except asyncio.CancelledError:
        print("[content_analyzer] CANCELLED during analysis")
        raise
    except Exception as e:
        print(f"[content_analyzer] ERROR: {e}")
        raise

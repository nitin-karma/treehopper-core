# summarizer/handler.py
import os
import ast
from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from treehopper.treehopper_llm import call_llm
from dotenv import load_dotenv
from .schema import SummarizerRequest

load_dotenv()
api_key = os.getenv("th_apikey")
DEFAULT_LLM_RETRIES = int(os.getenv("TH_LLM_RETRIES", "5"))


class SummarizerAgent:
    async def run(
        self,
        document_text: str,
        api_key: str | None,
        max_retries: int = DEFAULT_LLM_RETRIES,
    ) -> dict:
        prompt = f"""
You are a world-class business analyst. Summarize the following content in ~500 words,
preserving KPIs, metrics, timelines, decisions, and blockers.

Content:
{document_text}
"""
        try:
            llm = await call_llm(
                prompt=prompt, api_key=api_key, max_retries=max_retries
            )
        except Exception as e:
            err = f"Handler LLM call unexpected exception: {e}"
            print(err)
            return {"summary": f"[ERROR: {err}]"}

        print("summarizer: llm response keys:", list(llm.keys()))

        if "error" in llm:
            error = (llm.get("error") or "").strip()
            print(f"⚠️ Summarizer LLM error: {error}")
            return {"summary": f"[ERROR: {error}]"}

        safe = (llm.get("message") or "").strip()
        if safe == "":
            latency = llm.get("latency")
            tokens = llm.get("tokens")
            print(
                f"⚠️ Summarizer returned empty message (latency={latency}, tokens={tokens})"
            )
        return {"summary": safe}


@agent("summarizer", method="POST", goal="Summarize long executive documents")
async def handle(payload: SummarizerRequest = Body(...)):
    summary_input = payload.formatted

    try:
        summary_input = ast.literal_eval(f"'{summary_input}'")
    except Exception as e:
        print(f"Warning: failed to decode formatted string: {e}")

    ag = SummarizerAgent()
    return JSONResponse(
        await ag.run(summary_input, api_key, max_retries=DEFAULT_LLM_RETRIES)
    )

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


class SummarizerAgent:
    async def run(self, document_text: str, api_key: str | None) -> dict:
        prompt = f"""
You are a world-class business analyst. Summarize the following content in ~500 words,
preserving KPIs, metrics, timelines, decisions, and blockers.

Content:
{document_text}
"""
        llm = await call_llm(prompt=prompt, api_key=api_key)
        print(llm)
        if "error" in llm:
            error = (llm.get("error") or "").strip()
            print({"summary": error})
            return {"summary": ""}
        safe = (llm.get("message") or "").strip()
        return {"summary": safe}


@agent("summarizer", method="POST", goal="Summarize long executive documents")
async def handle(payload: SummarizerRequest = Body(...)):
    summary_input = payload.formatted

    # Decode formatter's escaped string → convert to real text
    try:
        summary_input = ast.literal_eval(f"'{summary_input}'")
    except Exception as e:
        print(str(e))

    ag = SummarizerAgent()
    return JSONResponse(await ag.run(summary_input, api_key))

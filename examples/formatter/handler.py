# formatter/handler.py
import os
from pathlib import Path
from fastapi import Body, HTTPException
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent, get_agent_id
from treehopper.treehopper_llm import call_llm
from .schema import FormatterRequest
from dotenv import load_dotenv

# import asyncio

load_dotenv()
api_key = os.getenv("th_apikey")
# allow overriding retries via env (optional)
DEFAULT_LLM_RETRIES = int(os.getenv("TH_LLM_RETRIES", "5"))
MAX_TEXT_FILE_SIZE = 200 * 1024  # 200 KB
agent_name = "formatter"
agent_id = get_agent_id(agent_name)


class FormatterAgent:
    async def run(
        self, doc_text: str, api_key: str | None, max_retries: int = DEFAULT_LLM_RETRIES
    ) -> dict:
        prompt = f"""
Sanitize the following text into a JSON-safe escaped string literal.
Output ONLY the escaped string literal (no quotes around it).

CONTENT:
{doc_text}
"""
        try:
            llm = await call_llm(
                prompt=prompt, api_key=api_key, max_retries=max_retries
            )
        except Exception as e:
            # Unexpected error from call_llm (shouldn't happen), surface it
            err = f"Handler LLM call unexpected exception: {e}"
            print(err)
            return {"formatted": f"[ERROR: {err}]"}

        # For debugging/observability in logs:
        print("formatter: llm response keys:", list(llm.keys()))

        if "error" in llm:
            error = (llm.get("error") or "").strip()
            # return explicit marker so tests/logs show failure reason
            print(f"⚠️ Formatter LLM error: {error}")
            return {"formatted": f"[ERROR: {error}]"}

        safe = (llm.get("message") or "").strip()
        # if empty string, still return explicit empty but log tokens/latency
        if safe == "":
            latency = llm.get("latency")
            tokens = llm.get("tokens")
            print(
                f"⚠️ Formatter returned empty message (latency={latency}, tokens={tokens})"
            )
        return {"formatted": safe}


@agent(
    "formatter", method="POST", goal="Format raw document into JSON-safe escaped string"
)
async def handle(payload: FormatterRequest = Body(...)):
    if payload.file_path is None:
        raise HTTPException(
            status_code=400, detail="The 'file_path' field is required in the payload."
        )
    file_path = payload.file_path.strip()

    if not file_path:
        raise HTTPException(
            status_code=400, detail="The 'file_path' field cannot be empty."
        )

    print(f"📩 Received file_path: {file_path}")

    resolved: Path | None = None

    abs_path = Path(file_path)
    if abs_path.is_absolute() and abs_path.exists():
        resolved = abs_path
    else:
        if agent_id is None:
            raise HTTPException(
                status_code=500,
                detail="Agent ID is missing. Cannot resolve shared paths.",
            )

        shared_base = (
            Path.home() / ".treehopper" / "registry" / "shared" / agent_id / "files"
        )
        rel_attempt = shared_base / file_path
        if rel_attempt.exists():
            resolved = rel_attempt
        else:
            fname_attempt = shared_base / Path(file_path).name
            if fname_attempt.exists():
                resolved = fname_attempt
            else:
                raise HTTPException(
                    status_code=404, detail=f"File not found: {file_path}"
                )

    if resolved is None:
        raise HTTPException(status_code=500, detail="Internal file resolution error.")

    print(f"📌 Resolved path → {resolved}")

    data = resolved.read_bytes()
    if len(data) > MAX_TEXT_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_TEXT_FILE_SIZE/1024:.0f}KB)",
        )

    doc_text = data.decode("utf-8", errors="ignore")
    print(f"length of the text - {len(doc_text)}")
    if not doc_text.strip():
        raise HTTPException(status_code=400, detail="File contains no readable text")

    ag = FormatterAgent()
    # propagate api_key and allow custom retries through env
    return JSONResponse(
        await ag.run(doc_text, api_key, max_retries=DEFAULT_LLM_RETRIES)
    )

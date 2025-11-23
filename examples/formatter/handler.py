# handler.py
import os
from pathlib import Path
from fastapi import Body, HTTPException
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent, get_agent_id
from treehopper.treehopper_llm import call_llm
from .schema import FormatterRequest
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("openai_api_key")
MAX_TEXT_FILE_SIZE = 200 * 1024  # 200 KB
agent_name = "formatter"
agent_id = get_agent_id(agent_name)


class FormatterAgent:
    async def run(self, doc_text: str, api_key: str | None) -> dict:
        prompt = f"""
Sanitize the following text into a JSON-safe escaped string literal.
Output ONLY the escaped string literal (no quotes around it).

CONTENT:
{doc_text}
"""
        llm = await call_llm(prompt=prompt, api_key=api_key)
        safe = llm.get("message", "").strip()
        return {"formatted": safe}


@agent(
    "formatter", method="POST", goal="Format raw document into JSON-safe escaped string"
)
async def handle(payload: FormatterRequest = Body(...)):
    # 💡 FIX 1: Check if file_path is None before calling .strip()
    if payload.file_path is None:
        raise HTTPException(
            status_code=400, detail="The 'file_path' field is required in the payload."
        )
    file_path = payload.file_path.strip()

    # Check for empty string after stripping
    if not file_path:
        raise HTTPException(
            status_code=400, detail="The 'file_path' field cannot be empty."
        )

    print(f"📩 Received file_path: {file_path}")

    # 💡 FIX 2: Initialize resolved to None to satisfy type checker
    resolved: Path | None = None  # Ensure it is defined with an explicit type

    # Case 1 — ABSOLUTE PATH
    abs_path = Path(file_path)
    if abs_path.is_absolute() and abs_path.exists():
        resolved = abs_path
    else:
        # 💡 FIX 3: Ensure agent_id is available before using it in a Path
        if agent_id is None:
            raise HTTPException(
                status_code=500,
                detail="Agent ID is missing. Cannot resolve shared paths.",
            )

        # Case 2 — SHARED RELATIVE (shared/<id>/files/...)
        shared_base = (
            Path.home() / ".treehopper" / "registry" / "shared" / agent_id / "files"
        )
        rel_attempt = shared_base / file_path
        if rel_attempt.exists():
            resolved = rel_attempt
        else:
            # Case 3 — just filename (test.txt)
            fname_attempt = shared_base / Path(file_path).name
            if fname_attempt.exists():
                resolved = fname_attempt
            else:
                raise HTTPException(
                    status_code=404, detail=f"File not found: {file_path}"
                )

    # 💡 FIX 4: Add unconditional check/assertion to satisfy MyPy
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
    if not doc_text.strip():
        raise HTTPException(status_code=400, detail="File contains no readable text")

    ag = FormatterAgent()
    return JSONResponse(await ag.run(doc_text, api_key))

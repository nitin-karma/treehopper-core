from typing import Optional
import fitz  # PyMuPDF
from treehopper.treehopper import agent
from treehopper.treehopper_llm import call_llm


@agent(
    "/api/v1/agents/pdf/summarize",
    method="POST",
    goal="Summarize uploaded PDF using LLM",
    tags=["Example Agents"],
)
async def pdf_summarize(
    file_path: str, provider: str = "openai", api_key: Optional[str] = None
):
    try:
        doc = fitz.open(file_path)
        text = "\n".join([page.get_text() for page in doc])
        summary = await call_llm(
            f"Summarize this PDF:\n{text[:5000]}", provider, api_key
        )
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}

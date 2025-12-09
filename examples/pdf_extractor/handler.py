import asyncio
import json
from pathlib import Path
from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from treehopper.th_config import TH_ROOT
from .schema import PdfExtractorRequest

agent_name = "pdf_extractor"
agent_id = get_agent_id(agent_name)


@agent("pdf_extractor", method="POST", goal="Extract text from PDF documents")
async def handle(payload: PdfExtractorRequest = Body(...)):
    run_id = get_run_id()

    print("[pdf_extractor] READY")
    await th_sleep(0)

    if run_id and await is_run_cancelled(run_id):
        print("[pdf_extractor] CANCEL detected before starting")
        raise asyncio.CancelledError()

    print(f"[pdf_extractor] Processing file: {payload.file_path}")

    try:
        import fitz

        if payload.file_path.startswith("shared/"):
            full_path = TH_ROOT / "registry" / payload.file_path
        else:
            full_path = Path(payload.file_path)

        if not full_path.exists():
            raise FileNotFoundError(f"PDF not found: {payload.file_path}")

        doc = fitz.open(str(full_path))
        total_pages = len(doc)

        print(f"[pdf_extractor] Found {total_pages} pages")

        text_parts = []
        for page_num in range(total_pages):
            if run_id and await is_run_cancelled(run_id):
                print(
                    f"[pdf_extractor] CANCEL detected at page {page_num+1}/{total_pages}"
                )
                doc.close()
                raise asyncio.CancelledError()

            page = doc[page_num]
            text = page.get_text()
            text_parts.append(text)

            print(f"[pdf_extractor] Processed page {page_num+1}/{total_pages}")
            await th_sleep(0.1)

        doc.close()

        full_text = "\n\n".join(text_parts)

        # Escape single quotes for shell safety
        safe_text = full_text.replace("'", "\\'")

        response = {
            "extracted_text": safe_text,
            "page_count": total_pages,
            "file_name": full_path.name,
        }

        # Print valid JSON (safe for shell piping)
        print(json.dumps(response, ensure_ascii=False))

        return response

    except asyncio.CancelledError:
        print("[pdf_extractor] CANCELLED during extraction")
        raise
    except Exception as e:
        print(f"[pdf_extractor] ERROR: {e}")
        raise

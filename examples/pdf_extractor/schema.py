from pydantic import BaseModel, Field

# from typing import Optional


class PdfExtractorRequest(BaseModel):
    file_path: str = Field(
        ..., description="Path to PDF file (e.g., shared/agent-id/files/document.pdf)"
    )


class PdfExtractorResponse(BaseModel):
    extracted_text: str = Field(..., description="Extracted text content")
    page_count: int = Field(..., description="Number of pages")
    file_name: str = Field(..., description="Original filename")

from pydantic import BaseModel, Field
from typing import List


class ReportGeneratorRequest(BaseModel):
    file_name: str = Field(..., description="Original filename")
    page_count: int = Field(..., description="Number of pages")
    sentiment: str = Field(..., description="Sentiment result")
    key_entities: List[str] = Field(default=[], description="Key entities")
    summary: str = Field(..., description="Summary text")
    themes: List[str] = Field(default=[], description="Main themes")


class ReportGeneratorResponse(BaseModel):
    report_markdown: str = Field(..., description="Full markdown report")
    report_title: str = Field(..., description="Report title")

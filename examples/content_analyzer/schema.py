from pydantic import BaseModel, Field
from typing import List


class ContentAnalyzerRequest(BaseModel):
    extracted_text: str = Field(..., description="Text content to analyze")
    file_name: str = Field(..., description="Original filename")
    page_count: int = Field(..., description="Number of pages")


class ContentAnalyzerResponse(BaseModel):
    sentiment: str = Field(..., description="Sentiment: positive/negative/neutral")
    key_entities: List[str] = Field(default=[], description="Key entities found")
    summary: str = Field(..., description="Brief content summary")
    themes: List[str] = Field(default=[], description="Main themes")
    file_name: str = Field(..., description="Original filename")
    page_count: int = Field(..., description="Number of pages")

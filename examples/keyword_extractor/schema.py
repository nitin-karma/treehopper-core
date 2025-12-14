from pydantic import BaseModel, Field
from typing import List


class KeywordExtractorRequest(BaseModel):
    extracted_text: str = Field(..., description="The raw extracted text to analyze")


class KeywordExtractorResponse(BaseModel):
    keywords: List[str] = Field(default=[], description="Extracted keywords")

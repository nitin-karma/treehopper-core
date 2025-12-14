from pydantic import BaseModel
from typing import List


class TeamsNotifierRequest(BaseModel):
    document_summary: str
    key_entities: List[str]
    sentiment: str

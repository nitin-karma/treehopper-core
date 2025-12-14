from pydantic import BaseModel
from typing import List


class ReviewQueueRequest(BaseModel):
    keywords_list: List[str]
    document_id: str
    review_reason: str

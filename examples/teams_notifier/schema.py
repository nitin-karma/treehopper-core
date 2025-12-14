from pydantic import BaseModel
from typing import List


class TeamsNotifierRequest(BaseModel):
    # Consumed from the merged output of the 'analyze' step
    sentiment: str
    keywords: List[str]

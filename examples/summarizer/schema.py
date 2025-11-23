from pydantic import BaseModel


class SummarizerRequest(BaseModel):
    formatted: str

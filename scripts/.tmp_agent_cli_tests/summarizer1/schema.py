from pydantic import BaseModel


class Summarizer1Request(BaseModel):
    name: str

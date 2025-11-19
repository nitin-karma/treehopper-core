from pydantic import BaseModel


class LlmcompareRequest(BaseModel):
    name: str

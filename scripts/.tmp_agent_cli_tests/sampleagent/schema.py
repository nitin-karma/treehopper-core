from pydantic import BaseModel


class SampleagentRequest(BaseModel):
    name: str

from pydantic import BaseModel


class SlowAgentRequest(BaseModel):
    name: str

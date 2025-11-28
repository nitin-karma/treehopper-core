from pydantic import BaseModel


class Slow_agentRequest(BaseModel):
    name: str

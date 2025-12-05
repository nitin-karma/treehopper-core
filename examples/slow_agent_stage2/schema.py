from pydantic import BaseModel


class SlowAgentStage2Request(BaseModel):
    step1_output: str

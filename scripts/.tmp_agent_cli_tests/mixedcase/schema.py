from pydantic import BaseModel


class MixedcaseRequest(BaseModel):
    name: str

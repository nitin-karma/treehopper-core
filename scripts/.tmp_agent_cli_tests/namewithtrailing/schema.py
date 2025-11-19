from pydantic import BaseModel


class NamewithtrailingRequest(BaseModel):
    name: str

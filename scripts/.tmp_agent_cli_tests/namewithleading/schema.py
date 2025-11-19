from pydantic import BaseModel


class NamewithleadingRequest(BaseModel):
    name: str

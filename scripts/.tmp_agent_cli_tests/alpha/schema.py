from pydantic import BaseModel


class AlphaRequest(BaseModel):
    name: str

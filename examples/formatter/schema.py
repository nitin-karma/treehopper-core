from pydantic import BaseModel


class FormatterRequest(BaseModel):
    file_path: str

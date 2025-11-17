from pydantic import BaseModel
from fastapi import Body
from treehopper.treehopper import agent


class GreetRequest(BaseModel):
    name: str


@agent(
    "greet",
    method="POST",
    goal="Greets a person by name",
    tags=["Example Agents"],
)
async def greet(request: GreetRequest = Body(None), name: str | None = None):
    """
    Supports:
    - HTTP POST { "name": "Nitin" }
    - Chaining: {"path": "/api/v1/agents/greet", "params": {"name": "Nitin"}}
    """

    # If chaining provided a primitive name param
    if name:
        return {"message": f"Hello {name}"}

    # If HTTP POST sent JSON body
    if request and request.name:
        return {"message": f"Hello {request.name}"}

    return {"error": "Missing name"}

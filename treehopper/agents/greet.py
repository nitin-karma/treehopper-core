from pydantic import BaseModel
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent


class GreetRequest(BaseModel):
    name: str


@agent(
    "/api/v1/agents/greet",
    method="POST",
    goal="Greets a person by name",
    tags=["Example Agents"],
)
async def greet(req: GreetRequest):
    message = f"Hello {req.name}"
    return JSONResponse({"message": message})

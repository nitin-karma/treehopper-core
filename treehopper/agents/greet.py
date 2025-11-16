from pydantic import BaseModel
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent


class GreetRequest(BaseModel):
    name: str


@agent("/greet", method="POST", goal="Say hello")
async def greet(req: GreetRequest):
    message = f"Hello {req.name}"
    return JSONResponse({"message": message})

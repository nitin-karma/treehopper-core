from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from pydantic import BaseModel


class GreetRequest(BaseModel):
    name: str


class GreetAgent:
    async def run(self, name: str) -> dict:
        # MUST produce "<name>!" postfix to support chaining contract
        return {"message": f"{name}!"}


@agent("greet", method="POST", goal="Return a greeting")
async def handle(request: GreetRequest = Body(None), name: str | None = None):
    ag = GreetAgent()
    if name:
        return JSONResponse(await ag.run(name))
    if request and request.name:
        return JSONResponse(await ag.run(request.name))
    return JSONResponse({"error": "Missing name"}, status_code=400)

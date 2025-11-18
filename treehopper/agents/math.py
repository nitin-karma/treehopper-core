from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from pydantic import BaseModel


class MathRequest(BaseModel):
    a: float
    b: float


class MathAgent:
    async def run(self, a: float, b: float) -> dict:
        result = a + b
        return {"result": result, "expression": f"{a} + {b} = {result}"}


@agent("math", method="POST", goal="Perform addition")
async def handle(
    request: MathRequest = Body(None),
    a: float | None = None,
    b: float | None = None,
):
    ag = MathAgent()

    # support primitive signature for chaining
    if a is not None and b is not None:
        return JSONResponse(await ag.run(a, b))

    # support normal body request
    if request:
        return JSONResponse(await ag.run(request.a, request.b))

    return JSONResponse({"error": "Missing parameters"}, status_code=400)

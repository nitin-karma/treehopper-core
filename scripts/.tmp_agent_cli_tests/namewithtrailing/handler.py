from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from .schema import NamewithtrailingRequest


class NamewithtrailingAgent:
    async def run(self, name: str, short: bool = False) -> dict:
        if short:
            return {"message": f"{name}!"}
        return {"message": f"Hello {name} from namewithtrailing agent!"}


@agent(
    "namewithtrailing",
    method="POST",
    goal="Example agent created via `treehopper init`",
)
async def handle(
    request: NamewithtrailingRequest = Body(None),
    name: str | None = None,
    short: bool = False,
):
    ag = NamewithtrailingAgent()
    if name:
        return JSONResponse(await ag.run(name, short))
    if request and request.name:
        return JSONResponse(await ag.run(request.name, short))
    return JSONResponse({"error": "Missing name"}, status_code=400)

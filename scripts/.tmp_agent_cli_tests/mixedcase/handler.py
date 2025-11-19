from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from .schema import MixedcaseRequest


class MixedcaseAgent:
    async def run(self, name: str, short: bool = False) -> dict:
        if short:
            return {"message": f"{name}!"}
        return {"message": f"Hello {name} from mixedcase agent!"}


@agent("mixedcase", method="POST", goal="Example agent created via `treehopper init`")
async def handle(
    request: MixedcaseRequest = Body(None), name: str | None = None, short: bool = False
):
    ag = MixedcaseAgent()
    if name:
        return JSONResponse(await ag.run(name, short))
    if request and request.name:
        return JSONResponse(await ag.run(request.name, short))
    return JSONResponse({"error": "Missing name"}, status_code=400)

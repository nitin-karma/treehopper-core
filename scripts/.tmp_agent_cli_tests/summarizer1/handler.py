from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from .schema import Summarizer1Request


class Summarizer1Agent:
    async def run(self, name: str, short: bool = False) -> dict:
        if short:
            return {"message": f"{name}!"}
        return {"message": f"Hello {name} from summarizer1 agent!"}


@agent("summarizer1", method="POST", goal="Example agent created via `treehopper init`")
async def handle(
    request: Summarizer1Request = Body(None),
    name: str | None = None,
    short: bool = False,
):
    ag = Summarizer1Agent()
    if name:
        return JSONResponse(await ag.run(name, short))
    if request and request.name:
        return JSONResponse(await ag.run(request.name, short))
    return JSONResponse({"error": "Missing name"}, status_code=400)

from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from .schema import Auto_agent_1Request


class Auto_agent_1Agent:
    async def run(self, name: str, short: bool = False) -> dict:
        if short:
            return {"message": f"{name}!"}
        return {"message": f"Hello {name} from auto_agent_1 agent!"}


@agent(
    "auto_agent_1", method="POST", goal="Example agent created via `treehopper init`"
)
async def handle(
    request: Auto_agent_1Request = Body(None),
    name: str | None = None,
    short: bool = False,
):
    ag = Auto_agent_1Agent()
    if name:
        return JSONResponse(await ag.run(name, short))
    if request and request.name:
        return JSONResponse(await ag.run(request.name, short))
    return JSONResponse({"error": "Missing name"}, status_code=400)

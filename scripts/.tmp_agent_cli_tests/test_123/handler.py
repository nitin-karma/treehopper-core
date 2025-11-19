from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from .schema import Test_123Request


class Test_123Agent:
    async def run(self, name: str, short: bool = False) -> dict:
        if short:
            return {"message": f"{name}!"}
        return {"message": f"Hello {name} from test_123 agent!"}


@agent("test_123", method="POST", goal="Example agent created via `treehopper init`")
async def handle(
    request: Test_123Request = Body(None), name: str | None = None, short: bool = False
):
    ag = Test_123Agent()
    if name:
        return JSONResponse(await ag.run(name, short))
    if request and request.name:
        return JSONResponse(await ag.run(request.name, short))
    return JSONResponse({"error": "Missing name"}, status_code=400)

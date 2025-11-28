# handler.py
import asyncio
from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent, get_agent_id
from .schema import Slow_agentRequest

agent_name = "slow_agent"
agent_id = get_agent_id(agent_name)


class Slow_agentAgent:
    async def run(self, name: str) -> dict:
        # ⏳ REAL SLOW OPERATION (10 seconds)
        for i in range(10):
            await asyncio.sleep(1)  # wait 1 sec each loop
            print(f"[slow_agent] working... {i+1}/10")

        return {"message": f"Hello {name} from slow_agent agent!"}


@agent(
    "slow_agent", method="POST", goal="Long-running slow agent for cancellation tests"
)
async def handle(payload: Slow_agentRequest = Body(...)):
    ag = Slow_agentAgent()
    result = await ag.run(payload.name)
    return JSONResponse(result)

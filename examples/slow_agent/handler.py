import asyncio
from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from .schema import SlowAgentRequest

agent_name = "slow_agent"
agent_id = get_agent_id(agent_name)


@agent("slow_agent", method="POST")
async def handle(payload: SlowAgentRequest = Body(...)):
    run_id = get_run_id()

    # 1) READY signal: early ACK so test harness can poll status safely
    print("[slow_agent] READY")

    # yield control so filesystem / runtime can create cancel marker or update status
    await th_sleep(0)

    # quick pre-check
    if run_id and await is_run_cancelled(run_id):
        print("[slow_agent] CANCEL detected BEFORE starting work")
        raise asyncio.CancelledError()

    print("[slow_agent] Step1 starting...")

    # do work, responsive to cancellation via th_sleep
    for i in range(20):
        print(f"[slow_agent] working... {i+1}/20")
        try:
            await th_sleep(0.2)
        except asyncio.CancelledError:
            print("[slow_agent] CANCEL detected DURING work")
            raise

    return {"step1_output": payload.name}

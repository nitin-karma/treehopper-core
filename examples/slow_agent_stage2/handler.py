import asyncio
from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from .schema import SlowAgentStage2Request

agent_name = "slow_agent_stage2"
agent_id = get_agent_id(agent_name)


@agent("slow_agent_stage2", method="POST")
async def handle(payload: SlowAgentStage2Request = Body(...)):
    run_id = get_run_id()

    # READY signal
    print("[slow_agent_stage2] READY")
    await th_sleep(0)

    if run_id and await is_run_cancelled(run_id):
        print("[slow_agent_stage2] CANCEL detected BEFORE work")
        raise asyncio.CancelledError()

    print("[slow_agent_stage2] Step2 starting...")

    for i in range(100):
        print(f"[slow_agent_stage2] working... {i+1}/5")
        try:
            await th_sleep(1)
        except asyncio.CancelledError:
            print("[slow_agent_stage2] CANCEL detected DURING work")
            raise

    return {"final_message": f"Processed {payload.step1_output}"}

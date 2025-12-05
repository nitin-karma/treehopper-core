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

    # 1️⃣ READY signal (industry-standard early ACK)
    print("[slow_agent] READY")

    # Give event loop a moment to process FS cancel file
    await th_sleep(0)  # yields control, no artificial delay

    # 2️⃣ Cancel BEFORE starting main loop
    if run_id and await is_run_cancelled(run_id):
        print("[slow_agent] CANCEL detected BEFORE starting work")
        raise asyncio.CancelledError()

    print("[slow_agent] Step1 starting...")

    # 3️⃣ Main loop
    for i in range(100):
        print(f"[slow_agent] working... {i+1}/5")

        try:
            await th_sleep(1)  # auto checks cancel at await boundaries
        except asyncio.CancelledError:
            print("[slow_agent] CANCEL detected DURING work")
            raise

    return {"step1_output": payload.name}

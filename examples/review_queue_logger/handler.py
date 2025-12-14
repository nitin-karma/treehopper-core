import asyncio
from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from .schema import ReviewQueueRequest

agent_name = "review_queue_logger"
agent_id = get_agent_id(agent_name)


@agent("review_queue_logger", method="POST")
async def handle(payload: ReviewQueueRequest = Body(...)):
    run_id = get_run_id()
    await th_sleep(0)  # Yield for cancellation guard

    if run_id and await is_run_cancelled(run_id):
        print("[review_queue_logger] CANCEL detected.")
        raise asyncio.CancelledError()

    review_id = f"REV-{hash(run_id)}"  # Generate a dummy review ID

    print(f"[review_queue_logger] Logging document {payload.document_id} for review.")
    print(f"[review_queue_logger] Reason: {payload.review_reason}")
    print(f"[review_queue_logger] Keywords found: {len(payload.keywords_list)}")

    # Simulated database insertion or queue push
    await th_sleep(0.5)

    return {"queue_item_id": review_id}

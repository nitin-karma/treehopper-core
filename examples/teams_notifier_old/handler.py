import asyncio
from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from .schema import TeamsNotifierRequest

agent_name = "teams_notifier"
agent_id = get_agent_id(agent_name)


@agent("teams_notifier", method="POST")
async def handle(payload: TeamsNotifierRequest = Body(...)):
    run_id = get_run_id()
    await th_sleep(0)  # Yield for cancellation guard

    if run_id and await is_run_cancelled(run_id):
        print("[teams_notifier] CANCEL detected.")
        raise asyncio.CancelledError()

    print(f"[teams_notifier] ⚠️ ALERT TRIGGERED for Run ID: {run_id}")
    print(f"[teams_notifier] Sentiment: {payload.sentiment}")
    print(f"[teams_notifier] Summary: {payload.document_summary[:50]}...")
    print(f"[teams_notifier] Entities: {', '.join(payload.key_entities)}")

    # Simulated API call to Teams/Slack
    await th_sleep(1)

    return {"notification_status": "SENT_CRITICAL"}

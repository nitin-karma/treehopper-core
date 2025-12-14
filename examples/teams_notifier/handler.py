import asyncio
from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from .schema import TeamsNotifierRequest

# from typing import List

# Assume constants or environment variables for agent details are set up
agent_name = "teams_notifier"
agent_id = get_agent_id(agent_name)


@agent("teams_notifier", method="POST")
async def handle(payload: TeamsNotifierRequest = Body(...)):
    """
    Handles critical alerts based on negative sentiment and low confidence.
    Consumes sentiment, keywords, and confidence from the previous step's merged output.
    """
    run_id = get_run_id()
    await th_sleep(0)  # Yield for cancellation guard

    if run_id and await is_run_cancelled(run_id):
        print("[teams_notifier] CANCEL detected.")
        raise asyncio.CancelledError()

    # --- Core Logic Update ---
    try:
        if payload.confidence:
            confidence = payload.confidence
    except Exception as e:
        print(str(e))
        confidence = 0.6

    # 1. Determine priority based on confidence (e.g., lower confidence = higher priority check)
    priority = "HIGH" if confidence < 0.8 else "MEDIUM"

    print(f"[teams_notifier] ⚠️ {priority} ALERT TRIGGERED for Run ID: {run_id}")
    print(f"[teams_notifier] Reason: Negative Sentiment ({payload.sentiment})")
    print(f"[teams_notifier] Model Confidence: {confidence:.2f}")

    # 2. Display the key data points for the analyst
    # Display top 5 keywords or all of them if fewer than 5
    keywords_to_show = (
        payload.keywords[:5] if len(payload.keywords) > 5 else payload.keywords
    )
    print(f"[teams_notifier] Key Terms: {', '.join(keywords_to_show)}")

    # Simulated API call to Teams/Slack
    await th_sleep(1)

    return {"notification_status": f"SENT_{priority}_ALERT"}

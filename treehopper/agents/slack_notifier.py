import httpx
from treehopper.treehopper import agent


@agent(
    "/notify_slack",
    method="POST",
    goal="Send a message to Slack via webhook",
    tags=["Example Agents"],
)
async def notify_slack(webhook_url: str, message: str):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(webhook_url, json={"text": message})
            return {"status": "sent", "response": r.status_code}
    except Exception as e:
        return {"error": str(e)}

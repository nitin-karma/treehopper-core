import pytest

# import asyncio
# from collections import deque

from treehopper.websockets.ws_manager import WSManager


class DummyWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)


@pytest.mark.asyncio
async def test_run_replay_buffer():
    ws_mgr = WSManager()
    run_id = "run-123"

    # Simulate events BEFORE connection
    await ws_mgr.broadcast(
        run_id=run_id,
        chain_name="demo_chain",
        event={"type": "step_start", "step_id": "extract"},
    )
    await ws_mgr.broadcast(
        run_id=run_id,
        chain_name="demo_chain",
        event={"type": "agent_start", "step_id": "extract", "agent": "pdf_extractor"},
    )

    # Late joiner
    ws = DummyWebSocket()
    await ws_mgr.connect_run(run_id, ws)

    assert len(ws.sent) == 2
    assert ws.sent[0]["type"] == "step_start"
    assert ws.sent[1]["type"] == "agent_start"


@pytest.mark.asyncio
async def test_chain_replay_buffer():
    ws_mgr = WSManager()
    chain = "demo_chain"
    run_id = "run-abc"

    await ws_mgr.broadcast(
        run_id=run_id,
        chain_name=chain,
        event={"type": "run_completed", "status": "success"},
    )

    ws = DummyWebSocket()
    await ws_mgr.connect_chain(chain, ws)

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_completed"
    assert ws.sent[0]["run_id"] == run_id

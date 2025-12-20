# treehopper/visualizer/ws_proxy.py
# import asyncio
import json
import websockets


async def proxy_chain_ws(chain_port: int, run_id: str, sink):
    url = f"ws://127.0.0.1:{chain_port}/api/v1/ws/run/{run_id}"
    async with websockets.connect(url) as ws:
        async for msg in ws:
            sink(json.loads(msg))

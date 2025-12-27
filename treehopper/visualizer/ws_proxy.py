# treehopper/visualizer/ws_proxy.py
# import asyncio
import json
import websockets
from websockets.exceptions import InvalidStatus, ConnectionClosed
from treehopper.th_config import DEFAULT_API_KEY

API_KEY = DEFAULT_API_KEY


async def proxy_chain_ws(chain_port: int, run_id: str, sink):
    url = f"ws://127.0.0.1:{chain_port}" f"/api/v1/ws/run/{run_id}?api_key={API_KEY}"

    try:
        async with websockets.connect(
            url,
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
        ) as ws:
            async for msg in ws:
                try:
                    sink(json.loads(msg))
                except Exception:
                    continue

    except InvalidStatus as e:
        # Chain runtime rejected WS (most common case)
        sink(
            {
                "type": "ws_error",
                "source": "chain_runtime",
                "message": f"WS rejected: {e.status_code}",
                "run_id": run_id,
            }
        )

    except ConnectionClosed:
        sink(
            {
                "type": "ws_closed",
                "run_id": run_id,
            }
        )

    except Exception as e:
        sink(
            {
                "type": "ws_exception",
                "error": str(e),
                "run_id": run_id,
            }
        )

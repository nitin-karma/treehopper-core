from collections import defaultdict, deque
from typing import Dict, Set
from fastapi import WebSocket
from treehopper.websockets.schema_guard import validate_event


class WSManager:
    def __init__(self):
        self.run_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.chain_connections: Dict[str, Set[WebSocket]] = defaultdict(set)

        # 🔁 Replay buffers
        self.run_buffers = defaultdict(lambda: deque(maxlen=200))
        self.chain_buffers = defaultdict(lambda: deque(maxlen=200))

    async def connect_run(self, run_id: str, websocket: WebSocket):
        self.run_connections[run_id].add(websocket)

        # 🔁 Replay
        for evt in self.run_buffers[run_id]:
            await websocket.send_json(evt)

    async def connect_chain(self, chain_name: str, websocket: WebSocket):
        self.chain_connections[chain_name].add(websocket)

        for evt in self.chain_buffers[chain_name]:
            await websocket.send_json(evt)

    async def disconnect(self, key: str, websocket: WebSocket, scope="run"):
        pool = self.run_connections if scope == "run" else self.chain_connections
        pool[key].discard(websocket)

    async def broadcast(self, run_id: str, chain_name: str, event: dict):
        # --- Run scope ---
        validate_event(event)
        self.run_buffers[run_id].append(event)
        for ws in list(self.run_connections.get(run_id, [])):
            try:
                await ws.send_json(event)
            except Exception:
                self.run_connections[run_id].discard(ws)

        # --- Chain scope ---
        chain_event = {**event, "run_id": run_id}
        self.chain_buffers[chain_name].append(chain_event)
        for ws in list(self.chain_connections.get(chain_name, [])):
            try:
                await ws.send_json(chain_event)
            except Exception:
                self.chain_connections[chain_name].discard(ws)


ws_manager = WSManager()

from collections import defaultdict, deque
from typing import Dict, Set
from pathlib import Path
from datetime import datetime
import json

from fastapi import WebSocket
from treehopper.websockets.schema_guard import validate_event
from treehopper.th_config import TH_ROOT
from treehopper.visualizer.analytics_recorder import (
    record_analytics_event,
    analytics_db_available,
)
from treehopper.logging import get_logger

logger = get_logger()


class WSManager:
    def __init__(self):
        # Active connections
        self.run_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.chain_connections: Dict[str, Set[WebSocket]] = defaultdict(set)

        # 🔁 In-memory replay buffers (fast path)
        self.run_buffers = defaultdict(lambda: deque(maxlen=200))
        self.chain_buffers = defaultdict(lambda: deque(maxlen=200))

    # ------------------------------------------------------------------
    # 🔁 File-backed event storage (durable replay)
    # ------------------------------------------------------------------

    def _run_event_file(self, run_id: str) -> Path:
        logger.info(f"Running event file for {run_id}")
        return TH_ROOT / "registry" / "chains" / "events" / f"{run_id}.events.jsonl"

    def _record_event(self, run_id: str, event: dict):
        """
        Append event to per-run JSONL file.
        """
        p = self._run_event_file(run_id)
        p.parent.mkdir(parents=True, exist_ok=True)

        enriched = dict(event)
        enriched["ts"] = datetime.utcnow().isoformat()

        with p.open("a") as f:
            logger.info(f"_record_event at {p} for {run_id}")
            f.write(json.dumps(enriched) + "\n")

    async def _replay_from_file(
        self, run_id: str, websocket: WebSocket, limit: int = 200
    ):
        """
        Replay last N events from disk for late joiners.
        """
        p = self._run_event_file(run_id)
        if not p.exists():
            return

        lines = p.read_text().splitlines()[-limit:]
        for line in lines:
            try:
                await websocket.send_text(line)
            except Exception as e:
                logger.error(str(e))
                break

    # ------------------------------------------------------------------
    # 🔌 Connection management
    # ------------------------------------------------------------------

    async def connect_run(self, run_id: str, websocket: WebSocket):
        # await websocket.accept()
        self.run_connections[run_id].add(websocket)

        # 🔁 Replay (file first, then memory)
        await self._replay_from_file(run_id, websocket)
        for evt in self.run_buffers[run_id]:
            await websocket.send_json(evt)

    async def connect_chain(self, chain_name: str, websocket: WebSocket):
        # await websocket.accept()
        self.chain_connections[chain_name].add(websocket)

        for evt in self.chain_buffers[chain_name]:
            await websocket.send_json(evt)

    async def disconnect(self, key: str, websocket: WebSocket, scope="run"):
        pool = self.run_connections if scope == "run" else self.chain_connections
        pool[key].discard(websocket)

    # ------------------------------------------------------------------
    # 📡 Broadcast
    # ------------------------------------------------------------------

    async def broadcast(self, run_id: str, chain_name: str, event: dict):
        """
        Broadcast event to:
        - run-level subscribers
        - chain-level subscribers
        Also records event for replay.
        """
        validate_event(event)

        # -------------------------------
        # Record (durable)
        # -------------------------------
        self._record_event(run_id, event)

        # B. Analytics sink (NEW)
        if analytics_db_available():
            try:
                record_analytics_event(run_id, chain_name, event)
            except Exception as e:
                # Never break runtime because of analytics
                logger.error(f"[analytics] failed: {str(e)}")
                pass

        # -------------------------------
        # Run scope
        # -------------------------------
        self.run_buffers[run_id].append(event)
        for ws in list(self.run_connections.get(run_id, [])):
            try:
                await ws.send_json(event)
            except Exception as e:
                logger.error(str(e))
                self.run_connections[run_id].discard(ws)

        # -------------------------------
        # Chain scope
        # -------------------------------
        chain_event = {**event, "run_id": run_id}
        self.chain_buffers[chain_name].append(chain_event)
        for ws in list(self.chain_connections.get(chain_name, [])):
            try:
                await ws.send_json(chain_event)
            except Exception as e:
                logger.error(str(e))
                self.chain_connections[chain_name].discard(ws)


ws_manager = WSManager()

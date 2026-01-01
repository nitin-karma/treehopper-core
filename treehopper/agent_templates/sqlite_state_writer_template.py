"""
Template: SQLite State Writer
Category: State
Description: Persist structured state into SQLite for workflows and ETL
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "sqlite_state_writer",
    "version": "1.0.0",
    "category": "state",
    "description": (
        "Persist structured state into SQLite. "
        "Used for workflow checkpoints, ETL pipelines, customer state, "
        "and deterministic recovery."
    ),
    "author": "TreehopperAI",
    "tags": ["sqlite", "state", "writer", "etl", "workflow"],
    "dependencies": ["sqlite3"],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Persist structured state into SQLite
inputs:
  - name: table
    type: string

  - name: data
    type: object

outputs:
  - name: success
    type: boolean
  - name: rows_affected
    type: number
version: "1.0"
"""

# ============================================================================
# HANDLER.PY  ✅ FORMAT-SAFE
# ============================================================================
HANDLER_CODE = """import sqlite3
from fastapi import Body

from treehopper.treehopper import agent, get_agent_id
from treehopper.agent_base import TreehopperAgentBase
from treehopper.th_config import TH_ROOT
from treehopper.logging import get_logger

from .schema import SQLiteStateWriterRequest, SQLiteStateWriterResponse

logger = get_logger()

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

DB_PATH = TH_ROOT / "state.db"


class SQLiteStateWriterAgent(TreehopperAgentBase):
    async def run(self, request: SQLiteStateWriterRequest) -> SQLiteStateWriterResponse:
        await self.check_cancel()

        table = request.table
        data = request.data or dict()

        if not table or not data:
            return SQLiteStateWriterResponse(
                success=False,
                rows_affected=0,
                error="Table or data missing"
            )

        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            keys = list(data.keys())
            placeholders = ",".join(["?"] * len(keys))

            sql = (
                "INSERT INTO "
                + table
                + " ("
                + ",".join(keys)
                + ") VALUES ("
                + placeholders
                + ")"
            )

            cur.execute(sql, [data[k] for k in keys])
            conn.commit()

            rows = cur.rowcount
            conn.close()

            return SQLiteStateWriterResponse(
                success=True,
                rows_affected=rows
            )

        except Exception as e:
            logger.exception("sqlite_state_writer failed")
            return SQLiteStateWriterResponse(
                success=False,
                rows_affected=0,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Persist structured state into SQLite")
async def handle(payload: SQLiteStateWriterRequest = Body(...)):
    agent = SQLiteStateWriterAgent()
    return (await agent.run(payload)).dict()
"""


# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel
from typing import Dict, Any, Optional


class SQLiteStateWriterRequest(BaseModel):
    table: str
    data: Dict[str, Any]


class SQLiteStateWriterResponse(BaseModel):
    success: bool = True
    rows_affected: int = 0
    error: Optional[str] = None
"""

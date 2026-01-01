"""
Template: SQLite State Reader
Category: State
Description: Deterministic SQLite state reader for workflows and ETL
"""

# ============================================================================
# TEMPLATE METADATA
# ============================================================================
TEMPLATE_INFO = {
    "name": "sqlite_state_reader",
    "version": "1.0.0",
    "category": "state",
    "description": "Read structured state from SQLite for deterministic workflows",
    "author": "TreehopperAI",
    "tags": ["sqlite", "state", "etl", "database"],
    "dependencies": ["sqlite3"],
}

# ============================================================================
# AGENT.YAML
# ============================================================================
AGENT_YAML = """agent_name: {agent_name}
agent_id: {agent_id}
subscription_id: {subscription_id}
entrypoint: /{agent_name}
description: Read structured state from SQLite
inputs:
  - name: table
    type: string

  - name: filters
    type: object
    required: false

  - name: limit
    type: number
    default: 10

outputs:
  - name: rows
    type: array
  - name: count
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

from .schema import SQLiteStateReaderRequest, SQLiteStateReaderResponse

logger = get_logger()

agent_name = "{agent_name}"
agent_id = get_agent_id(agent_name)

DB_PATH = TH_ROOT / "state.db"


class SQLiteStateReaderAgent(TreehopperAgentBase):
    async def run(self, request: SQLiteStateReaderRequest) -> SQLiteStateReaderResponse:
        await self.check_cancel()

        table = request.table
        filters = request.filters or dict()
        limit = request.limit or 10

        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            sql = "SELECT * FROM " + table
            params = []

            if filters:
                clauses = []
                for k, v in filters.items():
                    clauses.append(k + " = ?")
                    params.append(v)
                sql += " WHERE " + " AND ".join(clauses)

            sql += " LIMIT " + str(limit)

            cur.execute(sql, params)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

            conn.close()

            result_rows = []
            for row in rows:
                result_rows.append(dict(zip(columns, row)))

            return SQLiteStateReaderResponse(
                rows=result_rows,
                count=len(result_rows),
                success=True
            )

        except Exception as e:
            logger.exception("sqlite_state_reader failed")
            return SQLiteStateReaderResponse(
                rows=[],
                count=0,
                success=False,
                error=str(e)
            )


@agent("{agent_name}", method="POST", goal="Read structured state from SQLite")
async def handle(payload: SQLiteStateReaderRequest = Body(...)):
    agent = SQLiteStateReaderAgent()
    return (await agent.run(payload)).dict()
"""


# ============================================================================
# SCHEMA.PY
# ============================================================================
SCHEMA_CODE = """from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class SQLiteStateRequest(BaseModel):
    table: str
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = 10


class SQLiteStateResponse(BaseModel):
    rows: List[Dict[str, Any]] = []
    count: int = 0
    success: bool = True
    error: Optional[str] = None
"""

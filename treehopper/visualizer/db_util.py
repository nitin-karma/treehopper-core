# treehopper/visualizer/db_util
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from treehopper.th_config import TH_ROOT, DB_DIR, DASHBOARD_DB_NAME
from treehopper.logging import get_logger

logger = get_logger()


class DBManager:
    def __init__(self):
        self.db_path = Path(TH_ROOT) / DB_DIR / DASHBOARD_DB_NAME

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def execute(self, query: str, params: Tuple = ()) -> Optional[int]:
        logger.debug(f"Executing Query: {query} | Params: {params}")
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def fetch_one(self, query: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            conn.close()

    def fetch_all(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()


# Export a singleton instance
db = DBManager()

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class SessionState:
    def __init__(self, db_path: str = ".daggr_sessions.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        self._migrate_legacy_schema(cursor)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sheets (
                sheet_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                graph_name TEXT NOT NULL,
                name TEXT,
                transform TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        cursor.execute("PRAGMA table_info(sheets)")
        columns = [col[1] for col in cursor.fetchall()]
        if "transform" not in columns:
            cursor.execute("ALTER TABLE sheets ADD COLUMN transform TEXT")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sheets_user_graph 
            ON sheets(user_id, graph_name)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS node_inputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id TEXT,
                node_name TEXT,
                port_name TEXT,
                value TEXT,
                updated_at TEXT,
                FOREIGN KEY (sheet_id) REFERENCES sheets(sheet_id) ON DELETE CASCADE,
                UNIQUE(sheet_id, node_name, port_name)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_node_inputs_sheet 
            ON node_inputs(sheet_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS node_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id TEXT,
                node_name TEXT,
                result TEXT,
                created_at TEXT,
                FOREIGN KEY (sheet_id) REFERENCES sheets(sheet_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_node_results_sheet_node 
            ON node_results(sheet_id, node_name)
        """)

        conn.commit()
        conn.close()

    def _migrate_legacy_schema(self, cursor):
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='node_inputs'"
        )
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(node_inputs)")
            columns = [col[1] for col in cursor.fetchall()]
            if "session_id" in columns and "sheet_id" not in columns:
                cursor.execute("ALTER TABLE node_inputs RENAME TO _node_inputs_old")
                cursor.execute("ALTER TABLE node_results RENAME TO _node_results_old")
                cursor.execute("ALTER TABLE sessions RENAME TO _sessions_old")

                cursor.execute("""
                    CREATE TABLE sheets (
                        sheet_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        graph_name TEXT NOT NULL,
                        name TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE node_inputs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sheet_id TEXT,
                        node_name TEXT,
                        port_name TEXT,
                        value TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (sheet_id) REFERENCES sheets(sheet_id) ON DELETE CASCADE,
                        UNIQUE(sheet_id, node_name, port_name)
                    )
                """)
                cursor.execute("""
                    CREATE TABLE node_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sheet_id TEXT,
                        node_name TEXT,
                        result TEXT,
                        created_at TEXT,
                        FOREIGN KEY (sheet_id) REFERENCES sheets(sheet_id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    INSERT INTO sheets (sheet_id, user_id, graph_name, name, created_at, updated_at)
                    SELECT session_id, 'local', graph_name, 'Migrated Sheet', created_at, updated_at
                    FROM _sessions_old
                """)
                cursor.execute("""
                    INSERT INTO node_inputs (sheet_id, node_name, port_name, value, updated_at)
                    SELECT session_id, node_name, port_name, value, updated_at
                    FROM _node_inputs_old
                """)
                cursor.execute("""
                    INSERT INTO node_results (sheet_id, node_name, result, created_at)
                    SELECT session_id, node_name, result, created_at
                    FROM _node_results_old
                """)

                cursor.execute("DROP TABLE _sessions_old")
                cursor.execute("DROP TABLE _node_inputs_old")
                cursor.execute("DROP TABLE _node_results_old")

    def get_effective_user_id(self, hf_user: Optional[Dict] = None) -> Optional[str]:
        is_on_spaces = os.environ.get("SPACE_ID") is not None
        if hf_user and hf_user.get("username"):
            return hf_user["username"]
        if is_on_spaces:
            return None
        return "local"

    def create_sheet(
        self, user_id: str, graph_name: str, name: Optional[str] = None
    ) -> str:
        sheet_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        if not name:
            count = self.get_sheet_count(user_id, graph_name)
            name = f"Sheet {count + 1}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO sheets (sheet_id, user_id, graph_name, name, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sheet_id, user_id, graph_name, name, now, now),
        )
        conn.commit()
        conn.close()
        return sheet_id

    def get_sheet_count(self, user_id: str, graph_name: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM sheets WHERE user_id = ? AND graph_name = ?",
            (user_id, graph_name),
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def list_sheets(self, user_id: str, graph_name: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT sheet_id, name, created_at, updated_at 
               FROM sheets 
               WHERE user_id = ? AND graph_name = ?
               ORDER BY updated_at DESC""",
            (user_id, graph_name),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "sheet_id": row[0],
                "name": row[1],
                "created_at": row[2],
                "updated_at": row[3],
            }
            for row in rows
        ]

    def get_sheet(self, sheet_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT sheet_id, user_id, graph_name, name, transform, created_at, updated_at 
               FROM sheets WHERE sheet_id = ?""",
            (sheet_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            transform = None
            if row[4]:
                try:
                    transform = json.loads(row[4])
                except (json.JSONDecodeError, TypeError):
                    pass
            return {
                "sheet_id": row[0],
                "user_id": row[1],
                "graph_name": row[2],
                "name": row[3],
                "transform": transform,
                "created_at": row[5],
                "updated_at": row[6],
            }
        return None

    def save_transform(self, sheet_id: str, x: float, y: float, scale: float) -> bool:
        now = datetime.now().isoformat()
        transform = json.dumps({"x": x, "y": y, "scale": scale})
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sheets SET transform = ?, updated_at = ? WHERE sheet_id = ?",
            (transform, now, sheet_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def rename_sheet(self, sheet_id: str, new_name: str) -> bool:
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sheets SET name = ?, updated_at = ? WHERE sheet_id = ?",
            (new_name, now, sheet_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def delete_sheet(self, sheet_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM node_inputs WHERE sheet_id = ?", (sheet_id,))
        cursor.execute("DELETE FROM node_results WHERE sheet_id = ?", (sheet_id,))
        cursor.execute("DELETE FROM sheets WHERE sheet_id = ?", (sheet_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def get_or_create_sheet(
        self, user_id: str, graph_name: str, sheet_id: Optional[str] = None
    ) -> str:
        if sheet_id:
            sheet = self.get_sheet(sheet_id)
            if sheet and sheet["user_id"] == user_id:
                return sheet_id

        sheets = self.list_sheets(user_id, graph_name)
        if sheets:
            return sheets[0]["sheet_id"]

        return self.create_sheet(user_id, graph_name)

    def save_input(self, sheet_id: str, node_name: str, port_name: str, value: Any):
        now = datetime.now().isoformat()
        value_json = json.dumps(value, default=str)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO node_inputs (sheet_id, node_name, port_name, value, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(sheet_id, node_name, port_name) 
               DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (sheet_id, node_name, port_name, value_json, now),
        )
        cursor.execute(
            "UPDATE sheets SET updated_at = ? WHERE sheet_id = ?",
            (now, sheet_id),
        )
        conn.commit()
        conn.close()

    def get_inputs(self, sheet_id: str) -> Dict[str, Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT node_name, port_name, value FROM node_inputs WHERE sheet_id = ?",
            (sheet_id,),
        )
        results = cursor.fetchall()
        conn.close()
        inputs: Dict[str, Dict[str, Any]] = {}
        for node_name, port_name, value_json in results:
            if node_name not in inputs:
                inputs[node_name] = {}
            inputs[node_name][port_name] = json.loads(value_json)
        return inputs

    def save_result(self, sheet_id: str, node_name: str, result: Any):
        now = datetime.now().isoformat()
        result_json = json.dumps(result, default=str)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO node_results (sheet_id, node_name, result, created_at) VALUES (?, ?, ?, ?)",
            (sheet_id, node_name, result_json, now),
        )
        cursor.execute(
            "UPDATE sheets SET updated_at = ? WHERE sheet_id = ?",
            (now, sheet_id),
        )
        conn.commit()
        conn.close()

    def get_latest_result(self, sheet_id: str, node_name: str) -> Optional[Any]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT result FROM node_results 
               WHERE sheet_id = ? AND node_name = ? 
               ORDER BY created_at DESC LIMIT 1""",
            (sheet_id, node_name),
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            return json.loads(result[0])
        return None

    def get_result_by_index(
        self, sheet_id: str, node_name: str, index: int
    ) -> Optional[Any]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT result FROM node_results 
               WHERE sheet_id = ? AND node_name = ? 
               ORDER BY created_at ASC""",
            (sheet_id, node_name),
        )
        results = cursor.fetchall()
        conn.close()
        if results and 0 <= index < len(results):
            return json.loads(results[index][0])
        elif results:
            return json.loads(results[-1][0])
        return None

    def get_all_results(self, sheet_id: str) -> Dict[str, List[Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT node_name, result FROM node_results 
               WHERE sheet_id = ? 
               ORDER BY created_at ASC""",
            (sheet_id,),
        )
        results = cursor.fetchall()
        conn.close()
        all_results: Dict[str, List[Any]] = {}
        for node_name, result_json in results:
            if node_name not in all_results:
                all_results[node_name] = []
            all_results[node_name].append(json.loads(result_json))
        return all_results

    def get_sheet_state(self, sheet_id: str) -> Dict[str, Any]:
        return {
            "inputs": self.get_inputs(sheet_id),
            "results": self.get_all_results(sheet_id),
        }

    def clear_sheet_data(self, sheet_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM node_inputs WHERE sheet_id = ?", (sheet_id,))
        cursor.execute("DELETE FROM node_results WHERE sheet_id = ?", (sheet_id,))
        conn.commit()
        conn.close()

    def create_session(self, graph_name: str) -> str:
        return self.create_sheet("local", graph_name)

    def get_or_create_session(self, session_id: Optional[str], graph_name: str) -> str:
        return self.get_or_create_sheet("local", graph_name, session_id)

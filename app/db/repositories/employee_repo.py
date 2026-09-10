"""
app/db/repositories/employee_repo.py — Employee & Biometric Profile Repository
================================================================================
Handles personnel profiles, 512-dimensional ArcFace embeddings, and API users.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
from app.db.repositories.base import BaseRepository


def embedding_to_blob(embedding: np.ndarray) -> bytes:
    """Serialize float32 numpy vector to raw bytes."""
    return embedding.astype(np.float32).tobytes()


def blob_to_embedding(blob: bytes) -> np.ndarray:
    """Deserialize raw bytes back to 512-dim float32 numpy vector."""
    return np.frombuffer(blob, dtype=np.float32)


class EmployeeRepository(BaseRepository):

    def upsert(
        self,
        employee_id: str,
        name: str,
        department: str,
        embedding: np.ndarray,
        photo_path: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection as conn:
            conn.execute(
                """
                INSERT INTO employees (employee_id, name, department, embedding, photo_path, enrolled_at, active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(employee_id) DO UPDATE SET
                    name = excluded.name,
                    department = excluded.department,
                    embedding = excluded.embedding,
                    photo_path = COALESCE(excluded.photo_path, employees.photo_path),
                    enrolled_at = excluded.enrolled_at,
                    active = 1
                """,
                (employee_id, name, department, embedding_to_blob(embedding), photo_path, now),
            )

    def get_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetchone("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
        if not row:
            return None
        row["embedding"] = blob_to_embedding(row["embedding"])
        return row

    def get_all(self, active_only: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM employees WHERE active = 1" if active_only else "SELECT * FROM employees"
        rows = self._fetchall(sql)
        for r in rows:
            r["embedding"] = blob_to_embedding(r["embedding"])
        return rows

    def deactivate(self, employee_id: str) -> None:
        with self.connection as conn:
            conn.execute("UPDATE employees SET active = 0 WHERE employee_id = ?", (employee_id,))

    # API user management
    def create_api_user(self, username: str, hashed_password: str, role: str = "employee", employee_id: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO api_users
                    (username, hashed_password, role, employee_id, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (username, hashed_password, role, employee_id, now),
            )

    def get_api_user(self, username: str) -> Optional[Dict[str, Any]]:
        return self._fetchone("SELECT * FROM api_users WHERE username = ? AND active = 1", (username,))
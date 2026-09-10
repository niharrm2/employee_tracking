"""
app/db/repositories/base.py — Generic Repository Base Class
=============================================================
Provides query helper methods and shared connection handling.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.db.connection import get_connection


class BaseRepository:
    """Base repository for data-access abstractions."""

    @property
    def connection(self):
        return get_connection()

    def _fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        with self.connection as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def _fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self.connection as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def _execute(self, query: str, params: tuple = ()) -> int:
        with self.connection as conn:
            cur = conn.execute(query, params)
            return cur.lastrowid
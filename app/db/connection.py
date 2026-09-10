"""
app/db/connection.py — Thread-Safe SQLite Connection Manager
=============================================================
Enforces WAL mode, foreign key constraints, synchronous normal, and busy timeout.
"""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from typing import Optional

_db_path: str = "office_track.db"


def set_db_path(path: str) -> None:
    global _db_path
    _db_path = path


def get_db_path() -> str:
    return _db_path


@contextmanager
def get_connection():
    """
    Context manager returning a thread-safe connection with row_factory.
    Automatically commits on success or rolls back on exception.
    """
    conn = sqlite3.connect(_db_path, detect_types=sqlite3.PARSE_DECLTYPES, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
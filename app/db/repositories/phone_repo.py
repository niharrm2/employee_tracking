"""
app/db/repositories/phone_repo.py — Phone Usage Detection Repository
=====================================================================
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.db.repositories.base import BaseRepository


class PhoneRepository(BaseRepository):

    def insert(
        self,
        camera_id: str,
        detected_near_employee_id: Optional[str],
        confidence: float,
        snapshot_path: Optional[str],
        timestamp: str,
    ) -> int:
        return self._execute(
            """
            INSERT INTO phone_detections
                (camera_id, detected_near_employee_id, confidence, snapshot_path, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (camera_id, detected_near_employee_id, confidence, snapshot_path, timestamp),
        )

    def get_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM phone_detections WHERE timestamp LIKE ? ORDER BY timestamp DESC",
            (f"{date_str}%",),
        )
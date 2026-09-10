"""
app/db/repositories/alert_repo.py — Safety Hazard & Incident Alerts Repository
================================================================================
Stores optical fire/smoke alerts and acknowledgment states.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.db.repositories.base import BaseRepository


class AlertRepository(BaseRepository):

    def insert(
        self,
        camera_id: str,
        alert_type: str,
        confidence: float,
        snapshot_path: Optional[str],
        timestamp: str,
    ) -> int:
        return self._execute(
            """
            INSERT INTO fire_smoke_alerts
                (camera_id, alert_type, confidence, snapshot_path, timestamp, acknowledged)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (camera_id, alert_type, confidence, snapshot_path, timestamp),
        )

    def get_alerts(self, acknowledged: Optional[bool] = None, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM fire_smoke_alerts"
        params = []
        if acknowledged is not None:
            sql += " WHERE acknowledged = ?"
            params.append(1 if acknowledged else 0)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return self._fetchall(sql, tuple(params))

    def acknowledge(self, alert_id: int) -> None:
        with self.connection as conn:
            conn.execute("UPDATE fire_smoke_alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
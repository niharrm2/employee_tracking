"""
app/db/repositories/sighting_repo.py — Raw Sighting Events Repository
======================================================================
Stores biometric sighting occurrences for employees and unidentified visitors.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from app.db.repositories.base import BaseRepository


class SightingRepository(BaseRepository):

    def insert(
        self,
        employee_id: Optional[str],
        camera_id: str,
        zone: str,
        zone_type: str,
        confidence: Optional[float],
        event_type: str,
        snapshot_path: Optional[str],
        timestamp: str,
    ) -> int:
        return self._execute(
            """
            INSERT INTO sightings
                (employee_id, camera_id, zone, zone_type, confidence,
                 event_type, snapshot_path, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (employee_id, camera_id, zone, zone_type, confidence,
             event_type, snapshot_path, timestamp),
        )

    def get_by_date(self, date_str: str, employee_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM sightings WHERE timestamp LIKE ? AND event_type = 'known_face'"
        params = [f"{date_str}%"]
        if employee_id:
            sql += " AND employee_id = ?"
            params.append(employee_id)
        sql += " ORDER BY timestamp ASC"
        return self._fetchall(sql, tuple(params))

    def get_recent(self, minutes: int, zone_type: Optional[str] = None) -> List[Dict[str, Any]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        sql = """
            SELECT s.*, e.name, e.department
            FROM sightings s
            LEFT JOIN employees e ON s.employee_id = e.employee_id
            WHERE s.timestamp >= ? AND s.event_type = 'known_face'
        """
        params = [cutoff]
        if zone_type:
            sql += " AND s.zone_type = ?"
            params.append(zone_type)
        sql += " ORDER BY s.timestamp DESC"
        return self._fetchall(sql, tuple(params))

    def get_unknown_faces(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._fetchall(
            """
            SELECT * FROM sightings
            WHERE event_type = 'unknown_face'
            ORDER BY timestamp DESC LIMIT ?
            """,
            (limit,),
        )
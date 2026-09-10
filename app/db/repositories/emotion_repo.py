"""
app/db/repositories/emotion_repo.py — Emotion Telemetry Repository
===================================================================
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.db.repositories.base import BaseRepository


class EmotionRepository(BaseRepository):

    def insert(
        self,
        employee_id: Optional[str],
        camera_id: str,
        emotion: str,
        confidence: float,
        timestamp: str,
    ) -> int:
        return self._execute(
            """
            INSERT INTO emotion_readings
                (employee_id, camera_id, emotion, confidence, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (employee_id, camera_id, emotion, confidence, timestamp),
        )
"""
app/pipeline/processors/emotion_processor.py — Emotion Telemetry Processor
===========================================================================
"""
from __future__ import annotations
import logging
import numpy as np
from app.db.repositories.emotion_repo import EmotionRepository

logger = logging.getLogger(__name__)


class EmotionProcessor:
    def __init__(self, emotion_detector, emotion_repo: EmotionRepository = None):
        self.detector = emotion_detector
        self.repo = emotion_repo or EmotionRepository()

    def process(self, frame: np.ndarray, camera: dict, timestamp: str) -> None:
        if not self.detector:
            return
        emotions = self.detector.detect_emotions(frame)
        for em in emotions:
            self.repo.insert(
                employee_id=None,
                camera_id=camera["id"],
                emotion=em["dominant_emotion"],
                confidence=em["confidence"],
                timestamp=timestamp,
            )
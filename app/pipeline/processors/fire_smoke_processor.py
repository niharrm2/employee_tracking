"""
app/pipeline/processors/fire_smoke_processor.py — Optical Hazard Processor
============================================================================
"""
from __future__ import annotations
import logging
from typing import Optional
import numpy as np

from app.db.repositories.alert_repo import AlertRepository
from detectors.fire_smoke import FireSmokeDetector

logger = logging.getLogger(__name__)


class FireSmokeProcessor:
    def __init__(self, detector: FireSmokeDetector, alert_repo: Optional[AlertRepository] = None):
        self.detector = detector
        self.repo = alert_repo or AlertRepository()

    def process(
        self,
        frame: np.ndarray,
        camera: dict,
        timestamp: str,
        snapshot_path: Optional[str] = None,
    ) -> None:
        alerts = self.detector.detect(frame)
        for alert in alerts:
            self.repo.insert(
                camera_id=camera["id"],
                alert_type=alert["alert_type"],
                confidence=alert["confidence"],
                snapshot_path=snapshot_path,
                timestamp=timestamp,
            )
            logger.warning(
                "[HAZARD ALERT] %s detected at %s (camera: %s)",
                alert["alert_type"].upper(), camera["zone"], camera["id"]
            )
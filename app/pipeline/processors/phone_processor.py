"""
app/pipeline/processors/phone_processor.py — Mobile Phone Usage Processor
===========================================================================
"""
from __future__ import annotations
import logging
from typing import Optional
import numpy as np

from app.db.repositories.phone_repo import PhoneRepository
from detectors.phone import PhoneDetector, find_nearest_employee

logger = logging.getLogger(__name__)


class PhoneProcessor:
    def __init__(self, phone_detector: PhoneDetector, phone_repo: Optional[PhoneRepository] = None):
        self.detector = phone_detector
        self.repo = phone_repo or PhoneRepository()

    def process(
        self,
        frame: np.ndarray,
        camera: dict,
        timestamp: str,
        known_faces: list = None,
        snapshot_path: Optional[str] = None,
    ) -> None:
        phones = self.detector.detect_phones(frame)
        if not phones:
            return

        for phone in phones:
            nearest_emp = None
            if known_faces:
                nearest_emp = find_nearest_employee(phone["bbox"], known_faces)

            self.repo.insert(
                camera_id=camera["id"],
                detected_near_employee_id=nearest_emp,
                confidence=phone["confidence"],
                snapshot_path=snapshot_path,
                timestamp=timestamp,
            )
            logger.info(
                "Phone detected at %s (conf=%.2f, nearest_employee=%s)",
                camera["zone"], phone["confidence"], nearest_emp
            )
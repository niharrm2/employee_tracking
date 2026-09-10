"""
app/pipeline/processors/face_processor.py — Face Recognition & Sighting Processor
==================================================================================
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
import numpy as np

from app.db.repositories.sighting_repo import SightingRepository
from detectors.face_id import FaceDetector, process_frame_for_faces

logger = logging.getLogger(__name__)


class FaceProcessor:
    def __init__(
        self,
        face_detector: FaceDetector,
        sighting_repo: Optional[SightingRepository] = None,
        match_threshold: float = 0.4,
        det_score_threshold: float = 0.5,
        log_visitors: bool = True,
    ):
        self.detector = face_detector
        self.repo = sighting_repo or SightingRepository()
        self.match_threshold = match_threshold
        self.det_score_threshold = det_score_threshold
        self.log_visitors = log_visitors

    def process(
        self,
        frame: np.ndarray,
        camera: dict,
        timestamp: str,
        enrolled_employees: list,
        snapshot_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        known_faces, unknown_faces = process_frame_for_faces(
            frame,
            self.detector,
            enrolled_employees,
            match_threshold=self.match_threshold,
            det_score_threshold=self.det_score_threshold,
        )

        for face in known_faces:
            self.repo.insert(
                employee_id=face["employee_id"],
                camera_id=camera["id"],
                zone=camera["zone"],
                zone_type=camera["zone_type"],
                confidence=face["confidence"],
                event_type="known_face",
                snapshot_path=snapshot_path,
                timestamp=timestamp,
            )
            logger.debug("Known face: %s at %s (conf=%.2f)", face["employee_id"], camera["zone"], face["confidence"])

        if self.log_visitors:
            for _ in unknown_faces:
                self.repo.insert(
                    employee_id=None,
                    camera_id=camera["id"],
                    zone=camera["zone"],
                    zone_type=camera["zone_type"],
                    confidence=None,
                    event_type="unknown_face",
                    snapshot_path=snapshot_path,
                    timestamp=timestamp,
                )
                logger.debug("Unknown visitor face logged at %s", camera["zone"])

        return known_faces
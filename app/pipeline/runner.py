"""
app/pipeline/runner.py — Enterprise Detection Pipeline Runner
==============================================================
Runs continuously on CPU. Features:
  - Dynamic camera source routing (hot-swaps RTSP vs local MP4 on the fly from Settings)
  - Circuit breaker camera isolation (dead feeds fail-fast without hanging pipeline)
  - Connect-grab-disconnect sequential frame sampling
  - Reusable detector instances (models loaded once at startup)
  - Graceful shutdown handling
"""
from __future__ import annotations
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_config
from app.core.logging import setup_logging
from app.db.repositories.employee_repo import EmployeeRepository
from app.db.schema import init_db
from app.pipeline.circuit_breaker import CameraCircuitBreaker
from app.pipeline.frame_grabber import FrameGrabber
from app.pipeline.processors.face_processor import FaceProcessor
from app.pipeline.processors.phone_processor import PhoneProcessor
from app.pipeline.processors.fire_smoke_processor import FireSmokeProcessor
from app.pipeline.processors.emotion_processor import EmotionProcessor
from app.pipeline.scheduler import FeatureScheduler
from app.services.camera_svc import CameraService

from detectors.face_id import FaceDetector
from detectors.phone import PhoneDetector
from detectors.fire_smoke import FireSmokeDetector

logger = logging.getLogger("pipeline")
_RUNNING = True


def _handle_signal(sig, frame):
    global _RUNNING
    logger.info("Shutdown signal received (%s). Finishing active camera cycle...", sig)
    _RUNNING = False


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


class PipelineRunner:
    def __init__(self):
        self.cfg = get_config()
        self.camera_svc = CameraService()
        self.employee_repo = EmployeeRepository()

        # Shared infrastructure
        self.circuit_breaker = CameraCircuitBreaker(failure_threshold=3, cooldown_seconds=30.0)
        self.frame_grabber = FrameGrabber(
            timeout_seconds=self.cfg.capture_timeout,
            max_retries=self.cfg.capture_retries,
            retry_delay_seconds=self.cfg.capture_retry_delay,
            snapshots_enabled=self.cfg.snapshots_enabled,
            snapshots_dir=self.cfg.snapshots_dir,
            circuit_breaker=self.circuit_breaker,
        )
        self.scheduler = FeatureScheduler(self.cfg.sampling)

        # Detectors and Processors
        self.face_processor: Optional[FaceProcessor] = None
        self.phone_processor: Optional[PhoneProcessor] = None
        self.fire_processor: Optional[FireSmokeProcessor] = None
        self.emotion_processor: Optional[EmotionProcessor] = None

        self._init_processors()

    def _init_processors(self):
        feats = self.cfg.features
        thresh = self.cfg.thresholds

        if feats.get("face_recognition"):
            logger.info("Loading ArcFace model (%s)...", self.cfg.face_model_name)
            face_det = FaceDetector(
                model_name=self.cfg.face_model_name,
                det_size=self.cfg.face_det_size,
            )
            self.face_processor = FaceProcessor(
                face_detector=face_det,
                match_threshold=thresh.get("face_match_confidence", 0.4),
                det_score_threshold=thresh.get("min_face_detection_confidence", 0.5),
                log_visitors=feats.get("visitor_logging", True),
            )

        if feats.get("phone_detection"):
            logger.info("Loading YOLOv8n cell-phone detector...")
            phone_det = PhoneDetector(
                confidence_threshold=thresh.get("phone_detection_confidence", 0.5)
            )
            self.phone_processor = PhoneProcessor(phone_detector=phone_det)

        if feats.get("fire_smoke_detection"):
            logger.info("Loading optical fire/smoke heuristics...")
            fire_det = FireSmokeDetector(
                model_path=self.cfg.fire_model_path,
                fire_min_area=thresh.get("fire_min_area_ratio", 0.01),
                smoke_min_area=thresh.get("smoke_min_area_ratio", 0.05),
            )
            self.fire_processor = FireSmokeProcessor(detector=fire_det)

        if feats.get("emotion_detection"):
            from detectors.emotion import EmotionDetector
            emotion_det = EmotionDetector(min_confidence=thresh.get("emotion_min_confidence", 0.5))
            self.emotion_processor = EmotionProcessor(emotion_detector=emotion_det)

    def run_camera_cycle(self, camera: dict, enrolled: list) -> None:
        cam_id = camera["id"]
        feats = self.cfg.features

        # Check which features are due for this camera
        face_due = bool(self.face_processor and feats.get("face_recognition") and self.scheduler.is_due(cam_id, "face_recognition"))
        phone_due = bool(self.phone_processor and feats.get("phone_detection") and self.scheduler.is_due(cam_id, "phone_detection"))
        fire_due = bool(self.fire_processor and feats.get("fire_smoke_detection") and self.scheduler.is_due(cam_id, "fire_smoke_detection"))
        emotion_due = bool(self.emotion_processor and feats.get("emotion_detection") and self.scheduler.is_due(cam_id, "emotion_detection"))

        if not (face_due or phone_due or fire_due or emotion_due):
            return

        frame = self.frame_grabber.grab_frame(camera)
        if frame is None:
            # Mark attempted so we don't spam a failing camera
            for f, due in [("face_recognition", face_due), ("phone_detection", phone_due), ("fire_smoke_detection", fire_due), ("emotion_detection", emotion_due)]:
                if due:
                    self.scheduler.mark_executed(cam_id, f)
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        snapshot_path = None
        known_faces = []

        if face_due:
            snapshot_path = self.frame_grabber.save_snapshot(frame, cam_id, now_iso)
            known_faces = self.face_processor.process(frame, camera, now_iso, enrolled, snapshot_path)
            self.scheduler.mark_executed(cam_id, "face_recognition")

        if phone_due:
            if not snapshot_path:
                snapshot_path = self.frame_grabber.save_snapshot(frame, cam_id, now_iso)
            self.phone_processor.process(frame, camera, now_iso, known_faces, snapshot_path)
            self.scheduler.mark_executed(cam_id, "phone_detection")

        if fire_due:
            if not snapshot_path:
                snapshot_path = self.frame_grabber.save_snapshot(frame, cam_id, now_iso)
            self.fire_processor.process(frame, camera, now_iso, snapshot_path)
            self.scheduler.mark_executed(cam_id, "fire_smoke_detection")

        if emotion_due:
            self.emotion_processor.process(frame, camera, now_iso)
            self.scheduler.mark_executed(cam_id, "emotion_detection")

    def run(self) -> None:
        logger.info("Pipeline runner active. Monitoring cameras in mode: %s", self.camera_svc.get_mode().upper())

        while _RUNNING:
            try:
                # Dynamic hot-reload: query active cameras with current mode & RTSP URLs every sweep!
                cameras = self.camera_svc.get_effective_cameras()
                enrolled = self.employee_repo.get_all(active_only=True)

                for camera in cameras:
                    if not _RUNNING:
                        break
                    try:
                        self.run_camera_cycle(camera, enrolled)
                    except Exception as exc:
                        logger.error("Error processing camera %s: %s", camera["id"], exc, exc_info=True)

                time.sleep(1)

            except Exception as loop_exc:
                logger.error("Pipeline cycle exception: %s", loop_exc, exc_info=True)
                time.sleep(2)

        logger.info("Pipeline runner stopped cleanly.")
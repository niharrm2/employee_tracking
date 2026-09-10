"""
app/pipeline/frame_grabber.py — Resilient Connect-Grab-Disconnect Engine
=========================================================================
Acquires single frames from RTSP streams or local video files on demand.
Saves snapshots organized by camera and timestamp.
"""
from __future__ import annotations
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np

from app.pipeline.circuit_breaker import CameraCircuitBreaker

logger = logging.getLogger(__name__)


class FrameGrabber:
    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 1.0,
        snapshots_enabled: bool = True,
        snapshots_dir: str = "snapshots",
        circuit_breaker: Optional[CameraCircuitBreaker] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.snapshots_enabled = snapshots_enabled
        self.snapshots_dir = snapshots_dir
        self.circuit_breaker = circuit_breaker or CameraCircuitBreaker()

    def grab_frame(self, camera_dict: dict) -> Optional[np.ndarray]:
        """
        Grab a single fresh frame. Respects circuit breaker state to avoid
        stalling the pipeline on dead RTSP feeds.
        """
        cam_id = camera_dict["id"]
        source_url = camera_dict["source_url"]

        if not self.circuit_breaker.can_attempt(cam_id):
            logger.debug("Skipping camera %s — circuit breaker is OPEN", cam_id)
            return None

        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            cap = None
            try:
                is_net = source_url.startswith("rtsp://") or source_url.startswith("http://")
                is_webcam = source_url.isdigit()

                if is_webcam:
                    cap = cv2.VideoCapture(int(source_url))
                elif is_net:
                    cap = cv2.VideoCapture(source_url, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self.timeout_seconds * 1000))
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(self.timeout_seconds * 1000))
                else:
                    # Local video: compute continuous position by wall-clock time
                    cap = cv2.VideoCapture(source_url)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if total_frames > 1:
                        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                        frame_idx = int((time.time() * fps) % total_frames)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

                if not cap.isOpened():
                    raise ConnectionError(f"Could not open stream: {source_url}")

                ret, frame = cap.read()
                if not ret or frame is None:
                    raise ValueError("Stream opened but failed to read valid frame.")

                self.circuit_breaker.record_success(cam_id)
                return frame

            except Exception as exc:
                logger.warning(
                    "Frame grab failed for %s (%s) attempt %d/%d: %s",
                    cam_id, source_url, attempt, attempts, exc
                )
                if attempt < attempts:
                    time.sleep(self.retry_delay_seconds)
            finally:
                if cap is not None:
                    cap.release()

        self.circuit_breaker.record_failure(cam_id)
        return None

    def save_snapshot(self, frame: np.ndarray, camera_id: str, timestamp_iso: str) -> Optional[str]:
        """Save a frame to disk as a snapshot and return relative path."""
        if not self.snapshots_enabled:
            return None

        date_str = timestamp_iso[:10]
        save_dir = Path(self.snapshots_dir) / camera_id / date_str
        save_dir.mkdir(parents=True, exist_ok=True)

        safe_ts = timestamp_iso.replace(":", "-").replace(".", "-")
        filename = f"{safe_ts}.jpg"
        filepath = save_dir / filename

        try:
            cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return str(filepath)
        except Exception as exc:
            logger.warning("Failed to save snapshot: %s", exc)
            return None
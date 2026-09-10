"""
app/services/camera_svc.py — Camera Resolution & Dynamic Source Routing
=========================================================================
Implements the core requirement:
  - If camera_mode is "rtsp": uses custom RTSP URLs provided by user in Settings.
  - If camera_mode is "local": plays the local MP4 test video files in continuous loop.
  - Can test RTSP stream connectivity on-demand.
"""
from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
import cv2

from app.core.config import get_config
from app.db.repositories.settings_repo import SettingsRepository

logger = logging.getLogger(__name__)


class CameraService:
    def __init__(self, settings_repo: Optional[SettingsRepository] = None):
        self.settings_repo = settings_repo or SettingsRepository()
        self.cfg = get_config()

    def get_mode(self) -> str:
        """Returns active source mode: 'local' or 'rtsp'."""
        return self.settings_repo.get_camera_mode()

    def set_mode(self, mode: str) -> None:
        """Set active camera mode to 'local' or 'rtsp'."""
        self.settings_repo.set_camera_mode(mode)
        logger.info("Camera source mode switched to: %s", mode)

    def get_rtsp_urls(self) -> Dict[str, str]:
        """Returns configured RTSP stream URLs."""
        return self.settings_repo.get_rtsp_urls()

    def set_rtsp_urls(self, urls: Dict[str, str]) -> None:
        """Save user-provided RTSP stream URLs."""
        self.settings_repo.set_rtsp_urls(urls)
        logger.info("Updated RTSP stream URLs for %d cameras", len(urls))

    def get_effective_cameras(self) -> List[Dict[str, Any]]:
        """
        Returns all configured cameras with their resolved active source_url,
        taking into account whether the system is in 'rtsp' mode or 'local' mode.
        """
        mode = self.get_mode()
        custom_urls = self.get_rtsp_urls()
        result = []

        for cam in self.cfg.cameras:
            if not cam.enabled:
                continue

            cam_dict = cam.to_dict()
            cam_dict["mode"] = mode

            if mode == "rtsp":
                # Check if user provided an RTSP URL in settings
                custom_url = custom_urls.get(cam.id, "").strip()
                if custom_url:
                    cam_dict["source_url"] = custom_url
                    cam_dict["is_rtsp"] = True
                else:
                    # If camera URL in config starts with rtsp://, use it
                    if cam.rtsp_url.startswith("rtsp://") or cam.rtsp_url.startswith("http://"):
                        cam_dict["source_url"] = cam.rtsp_url
                        cam_dict["is_rtsp"] = True
                    else:
                        # Fallback to local file if RTSP URL not yet specified
                        cam_dict["source_url"] = cam.rtsp_url
                        cam_dict["is_rtsp"] = False
            else:
                # Local video files mode
                cam_dict["source_url"] = cam.rtsp_url
                cam_dict["is_rtsp"] = False

            cam_dict["stream_url"] = f"/api/v1/cameras/{cam.id}/stream"
            cam_dict["snapshot_url"] = f"/api/v1/cameras/{cam.id}/snapshot"
            result.append(cam_dict)

        return result

    def get_camera(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Find a camera and return its resolved config."""
        cameras = self.get_effective_cameras()
        for c in cameras:
            if c["id"] == camera_id:
                return c
        return None

    def test_connection(self, source_url: str, timeout_sec: float = 6.0) -> Dict[str, Any]:
        """
        Tests if an RTSP URL or local file can be opened and read.
        Returns latency in milliseconds and status information.
        """
        t0 = time.monotonic()
        cap = None
        try:
            is_net = source_url.startswith("rtsp://") or source_url.startswith("http://")
            if is_net:
                cap = cv2.VideoCapture(source_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout_sec * 1000))
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout_sec * 1000))
            else:
                cap = cv2.VideoCapture(source_url)

            if not cap.isOpened():
                return {
                    "status": "error",
                    "message": f"Unable to open video stream at {source_url}",
                    "latency_ms": None,
                }

            ret, frame = cap.read()
            latency = round((time.monotonic() - t0) * 1000, 1)

            if not ret or frame is None:
                return {
                    "status": "error",
                    "message": "Stream opened, but unable to decode any video frame",
                    "latency_ms": latency,
                }

            h, w = frame.shape[:2]
            return {
                "status": "ok",
                "message": f"Stream verified successfully ({w}x{h})",
                "resolution": f"{w}x{h}",
                "latency_ms": latency,
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Connection exception: {str(exc)}",
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            }
        finally:
            if cap is not None:
                cap.release()
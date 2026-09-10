"""
capture.py — RTSP Frame Grabbing
=================================
Opens an RTSP connection, grabs a single fresh frame, and immediately
closes the connection. This connect-grab-disconnect pattern keeps CPU
usage low by avoiding sustained RTSP stream decoding for all cameras.

NOTE: Frame timing accuracy is sampling-interval-limited. There is no
guarantee about the exact time offset between the frame timestamp and
the moment a face/object appears in a zone. All detection results should
be interpreted as "detected within the sampling window", not as precise
event times.
"""

import cv2
import logging
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def grab_frame(
    rtsp_url: str,
    timeout_seconds: float = 10.0,
    max_retries: int = 2,
    retry_delay_seconds: float = 1.0,
) -> Optional[np.ndarray]:
    """
    Connect to an RTSP stream, grab one frame, disconnect, and return it.

    Parameters
    ----------
    rtsp_url : str
        The RTSP URL of the camera (e.g. rtsp://user:pass@192.168.1.10/stream).
    timeout_seconds : float
        Maximum time to wait for the connection and a valid frame.
    max_retries : int
        Number of additional attempts after the first failure.
    retry_delay_seconds : float
        Seconds to wait between retries.

    Returns
    -------
    np.ndarray or None
        BGR frame as a numpy array, or None if capture failed after all retries.
    """
    attempts = max_retries + 1
    for attempt in range(1, attempts + 1):
        cap = None
        try:
            is_network = rtsp_url.startswith("rtsp://") or rtsp_url.startswith("http://")
            is_webcam = rtsp_url.isdigit()

            if is_webcam:
                cap = cv2.VideoCapture(int(rtsp_url))
            elif is_network:
                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout_seconds * 1000))
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout_seconds * 1000))
            else:
                # Local video file: open and advance based on elapsed wall-clock time
                cap = cv2.VideoCapture(rtsp_url)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames > 1:
                    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                    frame_idx = int((time.time() * fps) % total_frames)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

            if not cap.isOpened():
                raise ConnectionError(f"Could not open stream/file: {rtsp_url}")

            # Read one frame. The first read triggers the actual RTSP handshake.
            ret, frame = cap.read()
            if not ret or frame is None:
                raise ValueError("Stream opened but no frame received.")

            logger.debug(
                "Grabbed frame from %s (attempt %d/%d) — shape %s",
                rtsp_url, attempt, attempts, frame.shape,
            )
            return frame

        except Exception as exc:
            logger.warning(
                "Frame grab failed for %s (attempt %d/%d): %s",
                rtsp_url, attempt, attempts, exc,
            )
            if attempt < attempts:
                time.sleep(retry_delay_seconds)
        finally:
            if cap is not None:
                cap.release()

    logger.error(
        "All %d grab attempts failed for %s — skipping this cycle.", attempts, rtsp_url
    )
    return None


def grab_frame_from_config(camera_cfg: dict, capture_cfg: dict) -> Optional[np.ndarray]:
    """
    Convenience wrapper that accepts camera and capture config dicts
    (as parsed from config.yaml) and calls grab_frame with the right params.

    Parameters
    ----------
    camera_cfg : dict
        A single camera entry from config['cameras'].
    capture_cfg : dict
        The config['capture'] section.

    Returns
    -------
    np.ndarray or None
    """
    return grab_frame(
        rtsp_url=camera_cfg["rtsp_url"],
        timeout_seconds=capture_cfg.get("timeout_seconds", 10),
        max_retries=capture_cfg.get("max_retries", 2),
        retry_delay_seconds=capture_cfg.get("retry_delay_seconds", 1.0),
    )


def save_snapshot(
    frame: np.ndarray,
    base_dir: str,
    camera_id: str,
    timestamp: str,
) -> Optional[str]:
    """
    Save a frame as a JPEG snapshot and return the file path.

    Parameters
    ----------
    frame : np.ndarray
        BGR frame.
    base_dir : str
        Root directory for snapshots (e.g. "snapshots").
    camera_id : str
        Camera identifier used to create a subdirectory.
    timestamp : str
        ISO-8601 timestamp string used to build the filename.

    Returns
    -------
    str or None
        Relative path to the saved file, or None on failure.
    """
    import os

    # Build directory: snapshots/<camera_id>/<date>/
    date_str = timestamp[:10]  # "YYYY-MM-DD"
    save_dir = os.path.join(base_dir, camera_id, date_str)
    os.makedirs(save_dir, exist_ok=True)

    # Sanitise timestamp for filename
    safe_ts = timestamp.replace(":", "-").replace(".", "-")
    filename = f"{safe_ts}.jpg"
    filepath = os.path.join(save_dir, filename)

    try:
        cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return filepath
    except Exception as exc:
        logger.warning("Failed to save snapshot to %s: %s", filepath, exc)
        return None

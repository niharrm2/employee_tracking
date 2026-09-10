"""
api/routes/cameras.py — Live Camera Streams and Feed Endpoints
==============================================================
Provides:
  - GET /api/cameras               : List all configured cameras with status
  - GET /api/cameras/{id}/stream   : Live MJPEG video stream (renderable in <img src="...">)
  - GET /api/cameras/{id}/snapshot : Single live JPEG snapshot
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

_CONFIG_PATH = os.environ.get("OFFICE_TRACK_CONFIG", "config.yaml")


def load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class CameraInfo(BaseModel):
    id: str
    name: str
    zone: str
    zone_type: str
    enabled: bool
    stream_url: str
    snapshot_url: str


@router.get("", response_model=List[CameraInfo])
async def list_cameras():
    """List all enabled cameras for dashboard display."""
    cfg = load_config()
    cameras = cfg.get("cameras", [])
    result = []
    for c in cameras:
        if c.get("enabled", True):
            result.append(
                CameraInfo(
                    id=c["id"],
                    name=c["name"],
                    zone=c["zone"],
                    zone_type=c.get("zone_type", "work"),
                    enabled=c.get("enabled", True),
                    stream_url=f"/api/cameras/{c['id']}/stream",
                    snapshot_url=f"/api/cameras/{c['id']}/snapshot",
                )
            )
    return result


def _get_camera_by_id(camera_id: str) -> Optional[dict]:
    cfg = load_config()
    for c in cfg.get("cameras", []):
        if c["id"] == camera_id:
            return c
    return None


def _create_offline_frame(camera_name: str, width: int = 640, height: int = 360) -> bytes:
    """Generate a dark frame indicating camera is offline / connecting."""
    img = np.full((height, width, 3), 30, dtype=np.uint8)
    # Header bar
    cv2.rectangle(img, (0, 0), (width, 40), (20, 20, 20), -1)
    cv2.putText(
        img, f"CAMERA: {camera_name.upper()}",
        (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1
    )
    # Status text
    text = "OFFLINE / CONNECTING..."
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
    tx = (width - text_size[0]) // 2
    ty = (height + text_size[1]) // 2
    cv2.putText(img, text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 220), 2)

    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(camera_id: str):
    """Grab and return a single live JPEG snapshot from the camera."""
    cam = _get_camera_by_id(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    rtsp_url = cam["rtsp_url"]
    cap = cv2.VideoCapture(rtsp_url)
    try:
        ret, frame = cap.read()
        if not ret or frame is None:
            return Response(content=_create_offline_frame(cam["name"]), media_type="image/jpeg")

        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return Response(content=buf.tobytes(), media_type="image/jpeg")
    finally:
        cap.release()


async def mjpeg_frame_generator(camera: dict):
    """
    Yield multipart JPEG frames continuously at ~12 fps.
    Loops video files seamlessly when EOF is reached.
    """
    rtsp_url = camera["rtsp_url"]
    camera_name = camera["name"]

    is_network = rtsp_url.startswith("rtsp://") or rtsp_url.startswith("http://")
    if is_network:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    elif rtsp_url.isdigit():
        cap = cv2.VideoCapture(int(rtsp_url))
    else:
        cap = cv2.VideoCapture(rtsp_url)

    try:
        while True:
            if not cap.isOpened():
                frame_bytes = _create_offline_frame(camera_name)
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
                await asyncio.sleep(2.0)
                # Retry open
                cap.open(rtsp_url)
                continue

            ret, frame = cap.read()
            if not ret or frame is None:
                # Video file reached end — rewind to beginning
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames > 0:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()

                if not ret or frame is None:
                    frame_bytes = _create_offline_frame(camera_name)
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    )
                    await asyncio.sleep(1.0)
                    continue

            # Optional: resize if resolution is very large to conserve bandwidth & CPU
            h, w = frame.shape[:2]
            if w > 1280:
                frame = cv2.resize(frame, (1280, int(h * 1280 / w)))

            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            frame_bytes = buf.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )

            # Stream at ~12 FPS (80ms interval) for smooth video on CPU
            await asyncio.sleep(0.08)

    except asyncio.CancelledError:
        pass
    finally:
        cap.release()


@router.get("/{camera_id}/stream")
async def stream_camera(camera_id: str):
    """
    Stream live camera video as an MJPEG stream.
    Can be directly embedded in HTML with:
      <img src="/api/cameras/{camera_id}/stream" />
    """
    cam = _get_camera_by_id(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    return StreamingResponse(
        mjpeg_frame_generator(cam),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

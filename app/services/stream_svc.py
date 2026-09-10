"""
app/services/stream_svc.py — MJPEG Live Video Streaming & Snapshot Service
===========================================================================
Streams live video as multipart/x-mixed-replace JPEG batches.
Seamlessly loops local MP4 video files, reconnects RTSP streams on dropout,
and renders an enterprise dark telemetry placeholder frame if offline.
"""
from __future__ import annotations
import asyncio
import logging
from typing import AsyncGenerator, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def create_offline_frame(camera_name: str, width: int = 640, height: int = 360) -> bytes:
    """Generate an enterprise dark status frame when stream is offline/buffering."""
    img = np.full((height, width, 3), 18, dtype=np.uint8)
    # Header bar
    cv2.rectangle(img, (0, 0), (width, 36), (10, 14, 24), -1)
    cv2.putText(
        img, f"CHANNEL: {camera_name.upper()}",
        (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 175, 200), 1
    )
    # Central status notice
    msg = "CONNECTING / OFFLINE"
    sz = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
    cx = (width - sz[0]) // 2
    cy = (height + sz[1]) // 2
    cv2.putText(img, msg, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 220), 2)

    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


class StreamService:

    @staticmethod
    def get_snapshot(source_url: str, camera_name: str) -> bytes:
        """Grab a single fresh JPEG snapshot."""
        cap = None
        try:
            is_net = source_url.startswith("rtsp://") or source_url.startswith("http://")
            cap = cv2.VideoCapture(source_url, cv2.CAP_FFMPEG) if is_net else cv2.VideoCapture(source_url)
            ret, frame = cap.read()
            if not ret or frame is None:
                return create_offline_frame(camera_name)
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return buf.tobytes()
        except Exception:
            return create_offline_frame(camera_name)
        finally:
            if cap is not None:
                cap.release()

    @staticmethod
    async def generate_mjpeg(camera_dict: dict) -> AsyncGenerator[bytes, None]:
        """
        Asynchronously yield multipart/x-mixed-replace JPEG frames.
        Supports RTSP reconnections and endless local MP4 file rewinding.
        """
        source_url = camera_dict["source_url"]
        camera_name = camera_dict["name"]
        is_network = source_url.startswith("rtsp://") or source_url.startswith("http://")

        if is_network:
            cap = cv2.VideoCapture(source_url, cv2.CAP_FFMPEG)
        elif source_url.isdigit():
            cap = cv2.VideoCapture(int(source_url))
        else:
            cap = cv2.VideoCapture(source_url)

        try:
            while True:
                if not cap.isOpened():
                    offline_b = create_offline_frame(camera_name)
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + offline_b + b"\r\n"
                    )
                    await asyncio.sleep(2.0)
                    cap.open(source_url)
                    continue

                ret, frame = cap.read()
                if not ret or frame is None:
                    # If local file reached end, rewind to beginning
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if total_frames > 0:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()

                    if not ret or frame is None:
                        offline_b = create_offline_frame(camera_name)
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n" + offline_b + b"\r\n"
                        )
                        await asyncio.sleep(1.0)
                        continue

                # Downscale wide streams to 1280px max to conserve CPU & bandwidth
                h, w = frame.shape[:2]
                if w > 1280:
                    frame = cv2.resize(frame, (1280, int(h * 1280 / w)))

                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                frame_bytes = buf.tobytes()

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )

                # Cap streaming at ~12 FPS (~80ms) for smooth video without burning CPU
                await asyncio.sleep(0.08)

        except asyncio.CancelledError:
            pass
        finally:
            cap.release()
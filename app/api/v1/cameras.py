"""
app/api/v1/cameras.py — Camera Feeds & MJPEG Streams Router
============================================================
"""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_camera_service
from app.services.camera_svc import CameraService
from app.services.stream_svc import StreamService

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraOut(BaseModel):
    id: str
    name: str
    zone: str
    zone_type: str
    enabled: bool
    stream_url: str
    snapshot_url: str
    is_rtsp: bool
    mode: str


@router.get("", response_model=List[CameraOut])
async def list_cameras(cam_svc: CameraService = Depends(get_camera_service)):
    cams = cam_svc.get_effective_cameras()
    return [
        CameraOut(
            id=c["id"],
            name=c["name"],
            zone=c["zone"],
            zone_type=c["zone_type"],
            enabled=c.get("enabled", True),
            stream_url=c["stream_url"],
            snapshot_url=c["snapshot_url"],
            is_rtsp=c.get("is_rtsp", False),
            mode=c.get("mode", "local"),
        )
        for c in cams
    ]


@router.get("/{camera_id}/snapshot")
async def get_snapshot(camera_id: str, cam_svc: CameraService = Depends(get_camera_service)):
    cam = cam_svc.get_camera(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    buf = StreamService.get_snapshot(cam["source_url"], cam["name"])
    return Response(content=buf, media_type="image/jpeg")


@router.get("/{camera_id}/stream")
async def stream_mjpeg(camera_id: str, cam_svc: CameraService = Depends(get_camera_service)):
    cam = cam_svc.get_camera(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    return StreamingResponse(
        StreamService.generate_mjpeg(cam),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
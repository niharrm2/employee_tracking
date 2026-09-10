"""
app/api/v1/settings.py — System & Camera Source Settings Endpoints
====================================================================
Allows dynamic configuration of camera streaming source:
- Toggle between "local" (pre-recorded MP4 loops) and "rtsp" (live RTSP streams)
- Set and persist custom RTSP URLs per camera
- Test stream connectivity with latency and resolution checks
"""
from __future__ import annotations
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_camera_service, require_admin, TokenData
from app.services.camera_svc import CameraService

router = APIRouter(prefix="/settings", tags=["settings"])


class CameraSettingItem(BaseModel):
    id: str
    name: str
    zone: str
    zone_type: str
    default_source: str
    current_source: str
    rtsp_url: str
    is_rtsp: bool


class CameraSettingsResponse(BaseModel):
    camera_mode: str  # "local" or "rtsp"
    cameras: List[CameraSettingItem]


class UpdateCameraSettingsRequest(BaseModel):
    camera_mode: str  # "local" or "rtsp"
    rtsp_urls: Dict[str, str] = {}


class TestConnectionRequest(BaseModel):
    url: str
    timeout_seconds: Optional[float] = 6.0


class TestConnectionResponse(BaseModel):
    status: str
    message: str
    resolution: Optional[str] = None
    latency_ms: Optional[float] = None


@router.get("/cameras", response_model=CameraSettingsResponse)
async def get_camera_settings(
    cam_svc: CameraService = Depends(get_camera_service),
    current_user: TokenData = Depends(require_admin),
):
    """Retrieve current camera mode and configured stream sources."""
    mode = cam_svc.get_mode()
    rtsp_urls = cam_svc.get_rtsp_urls()
    effective = cam_svc.get_effective_cameras()

    items = []
    for c in effective:
        items.append(
            CameraSettingItem(
                id=c["id"],
                name=c["name"],
                zone=c["zone"],
                zone_type=c["zone_type"],
                default_source=c["rtsp_url"],
                current_source=c["source_url"],
                rtsp_url=rtsp_urls.get(c["id"], ""),
                is_rtsp=c["is_rtsp"],
            )
        )

    return CameraSettingsResponse(camera_mode=mode, cameras=items)


@router.put("/cameras", response_model=CameraSettingsResponse)
async def update_camera_settings(
    payload: UpdateCameraSettingsRequest,
    cam_svc: CameraService = Depends(get_camera_service),
    current_user: TokenData = Depends(require_admin),
):
    """Update camera mode ('local' vs 'rtsp') and custom RTSP URLs."""
    if payload.camera_mode not in ("local", "rtsp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid camera_mode. Must be either 'local' or 'rtsp'.",
        )

    cam_svc.set_mode(payload.camera_mode)
    cam_svc.set_rtsp_urls(payload.rtsp_urls)

    return await get_camera_settings(cam_svc=cam_svc, current_user=current_user)


@router.post("/cameras/test", response_model=TestConnectionResponse)
async def test_stream_connectivity(
    payload: TestConnectionRequest,
    cam_svc: CameraService = Depends(get_camera_service),
    current_user: TokenData = Depends(require_admin),
):
    """Test network or file connectivity for a video stream URL."""
    res = cam_svc.test_connection(payload.url, timeout_sec=payload.timeout_seconds or 6.0)
    return TestConnectionResponse(**res)
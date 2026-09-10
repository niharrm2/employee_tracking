"""
app/api/v1/alerts.py — Incident & Safety Alerts Router
========================================================
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_alert_service, require_any_role, require_admin_hr_manager, TokenData
from app.services.alert_svc import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


class FireAlertOut(BaseModel):
    id: int
    camera_id: str
    alert_type: str
    confidence: Optional[float]
    snapshot_path: Optional[str]
    timestamp: str
    acknowledged: bool


class UnknownFaceOut(BaseModel):
    id: int
    camera_id: str
    zone: str
    snapshot_path: Optional[str]
    timestamp: str


@router.get("/fire-smoke", response_model=List[FireAlertOut])
async def get_fire_alerts(
    acknowledged: Optional[bool] = None,
    limit: int = 100,
    svc: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(require_any_role),
):
    alerts = svc.get_fire_smoke_alerts(acknowledged=acknowledged, limit=limit)
    return [
        FireAlertOut(
            id=a["id"],
            camera_id=a["camera_id"],
            alert_type=a["alert_type"],
            confidence=a.get("confidence"),
            snapshot_path=a.get("snapshot_path"),
            timestamp=a["timestamp"],
            acknowledged=bool(a["acknowledged"]),
        )
        for a in alerts
    ]


@router.post("/fire-smoke/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    svc: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    svc.acknowledge_alert(alert_id)
    return {"message": f"Alert {alert_id} acknowledged"}


@router.get("/unknown-faces", response_model=List[UnknownFaceOut])
async def get_unknown_faces(
    limit: int = 50,
    svc: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(require_any_role),
):
    faces = svc.get_unknown_faces(limit=limit)
    return [
        UnknownFaceOut(
            id=f["id"],
            camera_id=f["camera_id"],
            zone=f["zone"],
            snapshot_path=f.get("snapshot_path"),
            timestamp=f["timestamp"],
        )
        for f in faces
    ]
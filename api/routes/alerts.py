"""
api/routes/alerts.py — Fire/Smoke Alerts + Unknown Face Endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

import database as db
from api.auth import require_admin_hr_manager, TokenData

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class FireSmokeAlert(BaseModel):
    id: int
    camera_id: str
    alert_type: str
    confidence: Optional[float]
    snapshot_path: Optional[str]
    timestamp: str
    acknowledged: bool


class UnknownFaceSighting(BaseModel):
    id: int
    camera_id: str
    zone: str
    zone_type: str
    snapshot_path: Optional[str]
    timestamp: str


@router.get("/fire-smoke", response_model=List[FireSmokeAlert])
async def get_fire_smoke_alerts(
    acknowledged: Optional[bool] = Query(default=None, description="Filter by acknowledged status"),
    limit: int = Query(default=100, le=500),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    """
    Retrieve fire/smoke alerts.

    ⚠️  These are supplementary heuristic signals — NOT certified fire alarms.
    Always maintain physical fire detection hardware as the primary system.
    """
    rows = db.get_fire_smoke_alerts(acknowledged=acknowledged, limit=limit)
    return [
        FireSmokeAlert(
            id=r["id"],
            camera_id=r["camera_id"],
            alert_type=r["alert_type"],
            confidence=r.get("confidence"),
            snapshot_path=r.get("snapshot_path"),
            timestamp=r["timestamp"],
            acknowledged=bool(r.get("acknowledged", 0)),
        )
        for r in rows
    ]


@router.post("/fire-smoke/{alert_id}/acknowledge")
async def acknowledge_fire_smoke_alert(
    alert_id: int,
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    """Mark a fire/smoke alert as acknowledged."""
    db.acknowledge_alert(alert_id)
    return {"message": f"Alert {alert_id} acknowledged"}


@router.get("/unknown-faces", response_model=List[UnknownFaceSighting])
async def get_unknown_faces(
    limit: int = Query(default=100, le=500),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    """Recent visitor/unknown face sightings from all cameras."""
    rows = db.get_unknown_face_sightings(limit=limit)
    return [
        UnknownFaceSighting(
            id=r["id"],
            camera_id=r["camera_id"],
            zone=r["zone"],
            zone_type=r["zone_type"],
            snapshot_path=r.get("snapshot_path"),
            timestamp=r["timestamp"],
        )
        for r in rows
    ]

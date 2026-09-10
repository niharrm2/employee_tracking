"""
app/api/v1/live.py — Real-Time Desk Presence Telemetry Router
==============================================================
"""
from __future__ import annotations
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_attendance_service, require_any_role, TokenData
from app.db.repositories.phone_repo import PhoneRepository
from app.services.attendance_svc import AttendanceService

router = APIRouter(prefix="/live", tags=["live"])


class LivePresence(BaseModel):
    employee_id: str
    name: Optional[str] = None
    department: Optional[str] = None
    zone: str
    zone_type: str
    camera_id: str
    last_seen: str
    timestamp: str
    confidence: Optional[float] = None


class PhoneDetectionOut(BaseModel):
    id: int
    camera_id: str
    detected_near_employee_id: Optional[str] = None
    confidence: Optional[float] = None
    timestamp: str


@router.get("/desk", response_model=List[LivePresence])
@router.get("", response_model=List[LivePresence])
async def get_live_desk_presence(
    window_minutes: int = Query(default=15, description="Minutes window"),
    minutes: Optional[int] = None,
    zone_type: Optional[str] = None,
    svc: AttendanceService = Depends(get_attendance_service),
    current_user: TokenData = Depends(require_any_role),
):
    win = minutes if minutes is not None else window_minutes
    records = svc.get_live_presence(window_minutes=win, zone_type=zone_type)
    return [
        LivePresence(
            employee_id=r["employee_id"],
            name=r.get("name") or r["employee_id"],
            department=r.get("department") or "Engineering",
            zone=r["zone"],
            zone_type=r["zone_type"],
            camera_id=r["camera_id"],
            last_seen=r.get("last_seen") or r["timestamp"],
            timestamp=r["timestamp"],
            confidence=r.get("confidence"),
        )
        for r in records
    ]


@router.get("/phone-detections", response_model=List[PhoneDetectionOut])
async def get_phone_detections(
    date_str: Optional[str] = Query(default=None, alias="date"),
    current_user: TokenData = Depends(require_any_role),
):
    target = date_str or date.today().isoformat()
    repo = PhoneRepository()
    rows = repo.get_by_date(target)
    return [
        PhoneDetectionOut(
            id=r["id"],
            camera_id=r["camera_id"],
            detected_near_employee_id=r.get("detected_near_employee_id"),
            confidence=r.get("confidence"),
            timestamp=r["timestamp"],
        )
        for r in rows
    ]
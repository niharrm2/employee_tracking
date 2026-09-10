"""
api/routes/live.py — Live Status Endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

import database as db
from api.auth import require_admin_hr_manager, TokenData

router = APIRouter(prefix="/api/live", tags=["live"])


class LivePresence(BaseModel):
    employee_id: str
    name: Optional[str]
    department: Optional[str]
    zone: str
    zone_type: str
    camera_id: str
    last_seen: str
    confidence: Optional[float]


class PhoneDetectionOut(BaseModel):
    id: int
    camera_id: str
    detected_near_employee_id: Optional[str]
    confidence: Optional[float]
    timestamp: str


@router.get("/desk", response_model=List[LivePresence])
async def get_live_desk_view(
    window_minutes: int = Query(
        default=10,
        description="Return sightings within the last N minutes. "
                    "Higher values = more lenient 'at desk' definition.",
    ),
    zone_type: Optional[str] = Query(default=None, description="Filter by zone_type"),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    """
    Who is currently at their desk / in a zone?

    Returns employees seen within the last `window_minutes`.
    Deduplicates by employee_id — returns only the most recent sighting per employee.

    NOTE: This is based on the sampling interval — an employee may have left
    after their last sighting without being detected. Treat as approximate.
    """
    rows = db.get_recent_sightings(minutes=window_minutes, zone_type=zone_type)

    # Deduplicate: keep only the most recent sighting per employee
    seen: dict = {}
    for r in rows:
        eid = r.get("employee_id")
        if eid and eid not in seen:
            seen[eid] = r

    return [
        LivePresence(
            employee_id=r["employee_id"],
            name=r.get("name"),
            department=r.get("department"),
            zone=r["zone"],
            zone_type=r["zone_type"],
            camera_id=r["camera_id"],
            last_seen=r["timestamp"],
            confidence=r.get("confidence"),
        )
        for r in seen.values()
    ]


@router.get("/phone-detections", response_model=List[PhoneDetectionOut])
async def get_recent_phone_detections(
    date_str: Optional[str] = Query(default=None, alias="date", description="YYYY-MM-DD"),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    """Phone detections for a given date (defaults to today)."""
    from datetime import date
    target = date_str or date.today().isoformat()
    rows = db.get_phone_detections(target)
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

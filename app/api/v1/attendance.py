"""
app/api/v1/attendance.py — Attendance Analytics Router
=======================================================
"""
from __future__ import annotations
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_attendance_service, require_any_role, TokenData
from app.services.attendance_svc import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])


class AttendanceOut(BaseModel):
    id: int
    employee_id: str
    name: Optional[str] = None
    department: Optional[str] = None
    date: str
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    presence_minutes: float = 0.0
    status: str = "absent"
    late_flag: bool = False
    early_leave_flag: bool = False
    last_zone: Optional[str] = None
    break_minutes: float = 0.0
    non_work_zone_minutes: float = 0.0
    computed_at: Optional[str] = None


@router.get("/daily", response_model=List[AttendanceOut])
async def get_daily_attendance(
    date_query: Optional[str] = Query(default=None, alias="date"),
    date_str: Optional[str] = Query(default=None),
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    svc: AttendanceService = Depends(get_attendance_service),
    current_user: TokenData = Depends(require_any_role),
):
    target = date_query or date_str or date.today().isoformat()
    if current_user.role == "employee":
        employee_id = current_user.employee_id or current_user.username

    records = svc.get_daily(target, employee_id, department)
    return [
        AttendanceOut(
            id=r["id"],
            employee_id=r["employee_id"],
            name=r.get("name") or r["employee_id"],
            department=r.get("department") or "Engineering",
            date=r["date"],
            check_in=r.get("check_in"),
            check_out=r.get("check_out"),
            presence_minutes=r.get("presence_minutes", 0),
            status=r.get("status", "absent"),
            late_flag=bool(r.get("late_flag")),
            early_leave_flag=bool(r.get("early_leave_flag")),
            last_zone=r.get("last_zone"),
            break_minutes=r.get("break_minutes", 0),
            non_work_zone_minutes=r.get("non_work_zone_minutes", 0),
            computed_at=r.get("computed_at"),
        )
        for r in records
    ]


@router.get("/range", response_model=List[AttendanceOut])
async def get_attendance_range(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    svc: AttendanceService = Depends(get_attendance_service),
    current_user: TokenData = Depends(require_any_role),
):
    if current_user.role == "employee":
        employee_id = current_user.employee_id or current_user.username

    records = svc.get_range(start_date, end_date, employee_id)
    if department:
        records = [r for r in records if r.get("department") and department.lower() in r["department"].lower()]

    return [
        AttendanceOut(
            id=r["id"],
            employee_id=r["employee_id"],
            name=r.get("name") or r["employee_id"],
            department=r.get("department") or "Engineering",
            date=r["date"],
            check_in=r.get("check_in"),
            check_out=r.get("check_out"),
            presence_minutes=r.get("presence_minutes", 0),
            status=r.get("status", "absent"),
            late_flag=bool(r.get("late_flag")),
            early_leave_flag=bool(r.get("early_leave_flag")),
            last_zone=r.get("last_zone"),
            break_minutes=r.get("break_minutes", 0),
            non_work_zone_minutes=r.get("non_work_zone_minutes", 0),
            computed_at=r.get("computed_at"),
        )
        for r in records
    ]


@router.get("/me", response_model=List[AttendanceOut])
async def get_my_attendance(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    svc: AttendanceService = Depends(get_attendance_service),
    current_user: TokenData = Depends(require_any_role),
):
    emp_id = current_user.employee_id or current_user.username
    records = svc.get_range(start_date, end_date, emp_id)
    return [
        AttendanceOut(
            id=r["id"],
            employee_id=r["employee_id"],
            name=r.get("name") or r["employee_id"],
            department=r.get("department") or "Engineering",
            date=r["date"],
            check_in=r.get("check_in"),
            check_out=r.get("check_out"),
            presence_minutes=r.get("presence_minutes", 0),
            status=r.get("status", "absent"),
            late_flag=bool(r.get("late_flag")),
            early_leave_flag=bool(r.get("early_leave_flag")),
            last_zone=r.get("last_zone"),
            break_minutes=r.get("break_minutes", 0),
            non_work_zone_minutes=r.get("non_work_zone_minutes", 0),
            computed_at=r.get("computed_at"),
        )
        for r in records
    ]


@router.get("", response_model=List[AttendanceOut])
async def get_attendance_generic(
    date_query: Optional[str] = Query(default=None, alias="date"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    svc: AttendanceService = Depends(get_attendance_service),
    current_user: TokenData = Depends(require_any_role),
):
    if start_date and end_date:
        return await get_attendance_range(
            start_date=start_date, end_date=end_date, employee_id=employee_id,
            department=department, svc=svc, current_user=current_user
        )
    return await get_daily_attendance(
        date_query=date_query, employee_id=employee_id,
        department=department, svc=svc, current_user=current_user
    )
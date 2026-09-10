"""
api/routes/attendance.py — Attendance Endpoints
"""
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

import database as db
from api.auth import require_admin_hr_manager, require_any_role, get_current_user, TokenData

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


class AttendanceRecord(BaseModel):
    employee_id: str
    name: Optional[str] = None
    department: Optional[str] = None
    date: str
    check_in: Optional[str]
    check_out: Optional[str]
    presence_minutes: float
    status: str
    late_flag: bool
    early_leave_flag: bool
    last_zone: Optional[str]
    break_minutes: float
    non_work_zone_minutes: float


@router.get("/daily", response_model=List[AttendanceRecord])
async def get_daily_attendance(
    date_str: str = Query(default=None, alias="date", description="YYYY-MM-DD, defaults to today"),
    department: Optional[str] = Query(default=None),
    employee_id: Optional[str] = Query(default=None),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    """
    Daily attendance summary for all employees or filtered by department/employee.
    Requires admin, hr, or manager role.
    """
    target_date = date_str or date.today().isoformat()
    rows = db.get_daily_attendance(target_date, employee_id=employee_id, department=department)
    return [
        AttendanceRecord(
            employee_id=r["employee_id"],
            name=r.get("name"),
            department=r.get("department"),
            date=r["date"],
            check_in=r.get("check_in"),
            check_out=r.get("check_out"),
            presence_minutes=r.get("presence_minutes", 0),
            status=r.get("status", "absent"),
            late_flag=bool(r.get("late_flag", 0)),
            early_leave_flag=bool(r.get("early_leave_flag", 0)),
            last_zone=r.get("last_zone"),
            break_minutes=r.get("break_minutes", 0),
            non_work_zone_minutes=r.get("non_work_zone_minutes", 0),
        )
        for r in rows
    ]


@router.get("/range", response_model=List[AttendanceRecord])
async def get_attendance_range(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    employee_id: Optional[str] = Query(default=None),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    """Date-range attendance data."""
    rows = db.get_attendance_range(start_date, end_date, employee_id=employee_id)
    return [
        AttendanceRecord(
            employee_id=r["employee_id"],
            name=r.get("name"),
            department=r.get("department"),
            date=r["date"],
            check_in=r.get("check_in"),
            check_out=r.get("check_out"),
            presence_minutes=r.get("presence_minutes", 0),
            status=r.get("status", "absent"),
            late_flag=bool(r.get("late_flag", 0)),
            early_leave_flag=bool(r.get("early_leave_flag", 0)),
            last_zone=r.get("last_zone"),
            break_minutes=r.get("break_minutes", 0),
            non_work_zone_minutes=r.get("non_work_zone_minutes", 0),
        )
        for r in rows
    ]


@router.get("/me", response_model=List[AttendanceRecord])
async def get_my_attendance(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    current_user: TokenData = Depends(require_any_role),
):
    """Employee self-service: own attendance records only."""
    if not current_user.employee_id:
        return []
    rows = db.get_attendance_range(start_date, end_date, employee_id=current_user.employee_id)
    return [
        AttendanceRecord(
            employee_id=r["employee_id"],
            name=r.get("name"),
            department=r.get("department"),
            date=r["date"],
            check_in=r.get("check_in"),
            check_out=r.get("check_out"),
            presence_minutes=r.get("presence_minutes", 0),
            status=r.get("status", "absent"),
            late_flag=bool(r.get("late_flag", 0)),
            early_leave_flag=bool(r.get("early_leave_flag", 0)),
            last_zone=r.get("last_zone"),
            break_minutes=r.get("break_minutes", 0),
            non_work_zone_minutes=r.get("non_work_zone_minutes", 0),
        )
        for r in rows
    ]

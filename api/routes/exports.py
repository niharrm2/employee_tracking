"""
api/routes/exports.py — CSV / Excel Export Endpoints
"""
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

import database as db
from api.auth import require_admin_or_hr, TokenData

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/attendance/csv")
async def export_attendance_csv(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    employee_id: Optional[str] = Query(default=None),
    current_user: TokenData = Depends(require_admin_or_hr),
):
    """Export attendance data as CSV."""
    import csv

    rows = db.get_attendance_range(start_date, end_date, employee_id=employee_id)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "employee_id", "name", "department", "date",
            "check_in", "check_out", "presence_minutes", "status",
            "late_flag", "early_leave_flag", "last_zone",
            "break_minutes", "non_work_zone_minutes",
        ],
    )
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "employee_id": r.get("employee_id", ""),
            "name": r.get("name", ""),
            "department": r.get("department", ""),
            "date": r.get("date", ""),
            "check_in": r.get("check_in", ""),
            "check_out": r.get("check_out", ""),
            "presence_minutes": r.get("presence_minutes", 0),
            "status": r.get("status", "absent"),
            "late_flag": "Yes" if r.get("late_flag") else "No",
            "early_leave_flag": "Yes" if r.get("early_leave_flag") else "No",
            "last_zone": r.get("last_zone", ""),
            "break_minutes": r.get("break_minutes", 0),
            "non_work_zone_minutes": r.get("non_work_zone_minutes", 0),
        })

    output.seek(0)
    filename = f"attendance_{start_date}_to_{end_date}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/attendance/excel")
async def export_attendance_excel(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    employee_id: Optional[str] = Query(default=None),
    current_user: TokenData = Depends(require_admin_or_hr),
):
    """Export attendance data as Excel (.xlsx)."""
    import pandas as pd

    rows = db.get_attendance_range(start_date, end_date, employee_id=employee_id)
    if not rows:
        rows = []

    df = pd.DataFrame(rows, columns=[
        "employee_id", "name", "department", "date",
        "check_in", "check_out", "presence_minutes", "status",
        "late_flag", "early_leave_flag", "last_zone",
        "break_minutes", "non_work_zone_minutes",
    ] if rows else [])

    # Map boolean flags
    if "late_flag" in df.columns:
        df["late_flag"] = df["late_flag"].map(lambda x: "Yes" if x else "No")
    if "early_leave_flag" in df.columns:
        df["early_leave_flag"] = df["early_leave_flag"].map(lambda x: "Yes" if x else "No")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")

    output.seek(0)
    filename = f"attendance_{start_date}_to_{end_date}.xlsx"
    return StreamingResponse(
        iter([output.read()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

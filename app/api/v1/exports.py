"""
app/api/v1/exports.py — Data Export Engine Router
==================================================
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Response
from app.api.deps import get_export_service, require_admin_or_hr, TokenData
from app.services.export_svc import ExportService

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/attendance/csv")
async def export_attendance_csv(
    start_date: str,
    end_date: str,
    employee_id: str = None,
    svc: ExportService = Depends(get_export_service),
    current_user: TokenData = Depends(require_admin_or_hr),
):
    csv_data = svc.export_csv(start_date, end_date, employee_id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{start_date}_{end_date}.csv"},
    )


@router.get("/attendance/excel")
async def export_attendance_excel(
    start_date: str,
    end_date: str,
    employee_id: str = None,
    svc: ExportService = Depends(get_export_service),
    current_user: TokenData = Depends(require_admin_or_hr),
):
    xlsx_bytes = svc.export_xlsx(start_date, end_date, employee_id)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=attendance_{start_date}_{end_date}.xlsx"},
    )
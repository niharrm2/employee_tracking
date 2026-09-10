"""
app/services/export_svc.py — Attendance Export Engine (CSV / XLSX)
===================================================================
"""
from __future__ import annotations
import csv
import io
from typing import List, Dict, Any
from app.services.attendance_svc import AttendanceService


class ExportService:
    def __init__(self, attendance_svc: AttendanceService = None):
        self.attendance_svc = attendance_svc or AttendanceService()

    def export_csv(self, start_date: str, end_date: str, employee_id: str = None) -> str:
        records = self.attendance_svc.get_range(start_date, end_date, employee_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Employee ID", "Name", "Department", "Date", "Check In", "Check Out",
            "Presence (Min)", "Status", "Late", "Early Leave", "Last Zone", "Break (Min)"
        ])
        for r in records:
            writer.writerow([
                r.get("employee_id"), r.get("name"), r.get("department"), r.get("date"),
                r.get("check_in"), r.get("check_out"), r.get("presence_minutes"),
                r.get("status"), "YES" if r.get("late_flag") else "NO",
                "YES" if r.get("early_leave_flag") else "NO",
                r.get("last_zone"), r.get("break_minutes"),
            ])
        return output.getvalue()

    def export_xlsx(self, start_date: str, end_date: str, employee_id: str = None) -> bytes:
        import openpyxl
        records = self.attendance_svc.get_range(start_date, end_date, employee_id)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Attendance Rollup"
        headers = [
            "Employee ID", "Name", "Department", "Date", "Check In", "Check Out",
            "Presence (Min)", "Status", "Late", "Early Leave", "Last Zone", "Break (Min)"
        ]
        ws.append(headers)
        for r in records:
            ws.append([
                r.get("employee_id"), r.get("name"), r.get("department"), r.get("date"),
                r.get("check_in"), r.get("check_out"), r.get("presence_minutes"),
                r.get("status"), "YES" if r.get("late_flag") else "NO",
                "YES" if r.get("early_leave_flag") else "NO",
                r.get("last_zone"), r.get("break_minutes"),
            ])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
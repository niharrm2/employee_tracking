"""
app/db/repositories/attendance_repo.py — Attendance Records Repository
=======================================================================
Stores and retrieves daily aggregated attendance, shift checks, and historical queries.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.db.repositories.base import BaseRepository


class AttendanceRepository(BaseRepository):

    def upsert(self, record: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection as conn:
            conn.execute(
                """
                INSERT INTO daily_attendance
                    (employee_id, date, check_in, check_out, presence_minutes, status,
                     late_flag, early_leave_flag, last_zone, break_minutes,
                     non_work_zone_minutes, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(employee_id, date) DO UPDATE SET
                    check_in = excluded.check_in,
                    check_out = excluded.check_out,
                    presence_minutes = excluded.presence_minutes,
                    status = excluded.status,
                    late_flag = excluded.late_flag,
                    early_leave_flag = excluded.early_leave_flag,
                    last_zone = excluded.last_zone,
                    break_minutes = excluded.break_minutes,
                    non_work_zone_minutes = excluded.non_work_zone_minutes,
                    computed_at = excluded.computed_at
                """,
                (
                    record["employee_id"], record["date"],
                    record.get("check_in"), record.get("check_out"),
                    record.get("presence_minutes", 0),
                    record.get("status", "absent"),
                    int(record.get("late_flag", False)),
                    int(record.get("early_leave_flag", False)),
                    record.get("last_zone"),
                    record.get("break_minutes", 0),
                    record.get("non_work_zone_minutes", 0),
                    now,
                ),
            )

    def get_by_date(
        self,
        date_str: str,
        employee_id: Optional[str] = None,
        department: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT da.*, e.name, e.department
            FROM daily_attendance da
            JOIN employees e ON da.employee_id = e.employee_id
            WHERE da.date = ?
        """
        params = [date_str]
        if employee_id:
            sql += " AND da.employee_id = ?"
            params.append(employee_id)
        if department:
            sql += " AND e.department = ?"
            params.append(department)
        sql += " ORDER BY e.name"
        return self._fetchall(sql, tuple(params))

    def get_range(
        self,
        start_date: str,
        end_date: str,
        employee_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT da.*, e.name, e.department
            FROM daily_attendance da
            JOIN employees e ON da.employee_id = e.employee_id
            WHERE da.date BETWEEN ? AND ?
        """
        params = [start_date, end_date]
        if employee_id:
            sql += " AND da.employee_id = ?"
            params.append(employee_id)
        sql += " ORDER BY da.date, e.name"
        return self._fetchall(sql, tuple(params))
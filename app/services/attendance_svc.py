"""
app/services/attendance_svc.py — Attendance Analytics & Rollup Service
======================================================================
"""
from __future__ import annotations
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional
import pytz

from app.core.config import get_config
from app.db.repositories.attendance_repo import AttendanceRepository
from app.db.repositories.employee_repo import EmployeeRepository
from app.db.repositories.sighting_repo import SightingRepository


def normalize_date_str(d_str: Optional[str]) -> str:
    """Normalize date inputs (YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY) to standard YYYY-MM-DD."""
    if not d_str:
        return date.today().isoformat()
    s = d_str.strip()
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return s
    cleaned = s.replace('/', '-')
    parts = cleaned.split('-')
    if len(parts) == 3:
        if len(parts[2]) == 4:  # DD-MM-YYYY or MM-DD-YYYY
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        if len(parts[0]) == 4:  # YYYY-M-D
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return s


class AttendanceService:
    def __init__(
        self,
        attendance_repo: Optional[AttendanceRepository] = None,
        sighting_repo: Optional[SightingRepository] = None,
        employee_repo: Optional[EmployeeRepository] = None,
    ):
        self.attendance_repo = attendance_repo or AttendanceRepository()
        self.sighting_repo = sighting_repo or SightingRepository()
        self.employee_repo = employee_repo or EmployeeRepository()
        self.cfg = get_config()

    def rollup_for_date(self, date_str: str) -> None:
        """Compute attendance summary for all employees for a specific date."""
        target_date = normalize_date_str(date_str)
        employees = self.employee_repo.get_all(active_only=True)
        tz_name = getattr(self.cfg, "work_timezone", "Asia/Kolkata")
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.utc

        min_presence = self.cfg.thresholds.get("min_presence_minutes", 0.1)

        for emp in employees:
            emp_id = emp["employee_id"]
            sightings = self.sighting_repo.get_by_date(target_date, employee_id=emp_id)

            if not sightings:
                self.attendance_repo.upsert({
                    "employee_id": emp_id,
                    "date": target_date,
                    "check_in": None,
                    "check_out": None,
                    "presence_minutes": 0.0,
                    "status": "absent",
                    "late_flag": False,
                    "early_leave_flag": False,
                    "last_zone": None,
                    "break_minutes": 0.0,
                    "non_work_zone_minutes": 0.0,
                })
                continue

            timestamps = []
            for s in sightings:
                try:
                    dt = datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00"))
                    timestamps.append((dt, s))
                except Exception:
                    pass

            if not timestamps:
                continue

            timestamps.sort(key=lambda x: x[0])
            first_dt, _ = timestamps[0]
            last_dt, last_s = timestamps[-1]

            presence_min = max(0.1, round((last_dt - first_dt).total_seconds() / 60.0, 1))
            status = "present" if presence_min >= min_presence else "absent"

            # Check late arrival against work_start
            late_flag = False
            try:
                start_h, start_m = map(int, self.cfg.work_start.split(":"))
                local_in = first_dt.astimezone(tz)
                grace = self.cfg.work_grace_minutes
                if (local_in.hour * 60 + local_in.minute) > (start_h * 60 + start_m + grace):
                    late_flag = True
            except Exception:
                pass

            self.attendance_repo.upsert({
                "employee_id": emp_id,
                "date": target_date,
                "check_in": first_dt.isoformat(),
                "check_out": last_dt.isoformat(),
                "presence_minutes": presence_min,
                "status": status,
                "late_flag": late_flag,
                "early_leave_flag": False,
                "last_zone": last_s.get("zone", "Work Area"),
                "break_minutes": 0.0,
                "non_work_zone_minutes": 0.0,
            })

    def get_daily(
        self,
        date_str: str,
        employee_id: Optional[str] = None,
        department: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        norm_date = normalize_date_str(date_str)
        self.rollup_for_date(norm_date)
        return self.attendance_repo.get_by_date(norm_date, employee_id, department)

    def get_range(
        self,
        start_date: str,
        end_date: str,
        employee_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        s_norm = normalize_date_str(start_date)
        e_norm = normalize_date_str(end_date)
        today_str = date.today().isoformat()
        if s_norm <= today_str <= e_norm:
            self.rollup_for_date(today_str)
        return self.attendance_repo.get_range(s_norm, e_norm, employee_id)

    def get_live_presence(self, window_minutes: int = 15, zone_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns deduped sightings of employees active in the last N minutes."""
        sightings = self.sighting_repo.get_recent(window_minutes, zone_type)
        seen = {}
        for s in sightings:
            emp_id = s.get("employee_id")
            if emp_id and emp_id not in seen:
                item = dict(s)
                item["last_seen"] = s["timestamp"]
                seen[emp_id] = item
        return list(seen.values())
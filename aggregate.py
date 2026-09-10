"""
aggregate.py — Daily Attendance Rollup
========================================
Reads raw sightings from the database for a given date and computes
the daily_attendance summary for every employee.

Computed fields:
  - check_in       : timestamp of first sighting of the day
  - check_out      : timestamp of last sighting
  - presence_minutes: (check_out - check_in) in minutes
  - status         : 'present' if presence_minutes >= min_presence_threshold
  - late_flag      : check_in is after work_start + grace_period
  - early_leave_flag: check_out is before work_end - grace_period
  - last_zone      : zone from the most recent sighting
  - break_minutes  : sum of consecutive gaps > min_break_gap_minutes
  - non_work_zone_minutes: time estimated in non_work zone cameras

NOTE: All duration metrics are *estimates* bounded by the sampling
interval. A 15-second face-recognition interval means we can only
estimate presence/breaks with ~15-second granularity.

Usage:
    python aggregate.py                          # today
    python aggregate.py --date 2026-09-07        # specific date
    python aggregate.py --date 2026-09-01 --date-end 2026-09-07  # range
"""

import logging
import sys
from datetime import datetime, date, timedelta, time as dtime
from pathlib import Path
from typing import Dict, Any, List, Optional

import click
import yaml
import pytz
from rich.console import Console
from rich.table import Table

import database as db

console = Console()
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def parse_time(time_str: str) -> dtime:
    """Parse 'HH:MM' into a datetime.time object."""
    h, m = map(int, time_str.split(":"))
    return dtime(h, m)


def compute_daily_attendance(
    employee_id: str,
    date_str: str,
    sightings: List[Dict[str, Any]],
    work_schedule: Dict[str, Any],
    thresholds: Dict[str, Any],
    tz: pytz.BaseTzInfo,
) -> Dict[str, Any]:
    """
    Given all sightings for one employee on one day, compute attendance record.

    Parameters
    ----------
    employee_id : str
    date_str : str — "YYYY-MM-DD"
    sightings : list — sorted by timestamp ASC, pre-filtered for this employee+date
    work_schedule : dict — start_time, end_time, grace_period_minutes
    thresholds : dict — min_presence_minutes, min_break_gap_minutes
    tz : pytz timezone — for comparing against work schedule

    Returns
    -------
    dict matching daily_attendance table columns.
    """
    result = {
        "employee_id": employee_id,
        "date": date_str,
        "check_in": None,
        "check_out": None,
        "presence_minutes": 0.0,
        "status": "absent",
        "late_flag": False,
        "early_leave_flag": False,
        "last_zone": None,
        "break_minutes": 0.0,
        "non_work_zone_minutes": 0.0,
    }

    if not sightings:
        return result

    # Parse timestamps (stored as ISO-8601 UTC)
    def parse_ts(ts_str: str) -> datetime:
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.utc)
            return dt
        except ValueError:
            return datetime.fromisoformat(ts_str).replace(tzinfo=pytz.utc)

    timestamps = [parse_ts(s["timestamp"]) for s in sightings]
    timestamps.sort()

    check_in_dt = timestamps[0]
    check_out_dt = timestamps[-1]

    result["check_in"] = check_in_dt.isoformat()
    result["check_out"] = check_out_dt.isoformat()

    # Presence window (check-in to check-out)
    presence_minutes = (check_out_dt - check_in_dt).total_seconds() / 60.0
    result["presence_minutes"] = round(presence_minutes, 1)

    min_presence = thresholds.get("min_presence_minutes", 5)
    result["status"] = "present" if presence_minutes >= min_presence else "absent"

    # Last zone
    result["last_zone"] = sightings[-1].get("zone")

    # Late arrival check
    work_start_str = work_schedule.get("start_time", "09:00")
    grace = work_schedule.get("grace_period_minutes", 15)
    work_start = parse_time(work_start_str)
    work_end_str = work_schedule.get("end_time", "18:00")
    work_end = parse_time(work_end_str)

    # Convert check-in to local timezone for schedule comparison
    check_in_local = check_in_dt.astimezone(tz)
    check_out_local = check_out_dt.astimezone(tz)

    # Build aware datetime for work start/end on this date
    date_obj = date.fromisoformat(date_str)
    work_start_aware = tz.localize(datetime.combine(date_obj, work_start))
    work_end_aware = tz.localize(datetime.combine(date_obj, work_end))

    late_cutoff = work_start_aware + timedelta(minutes=grace)
    early_cutoff = work_end_aware - timedelta(minutes=grace)

    result["late_flag"] = check_in_local > late_cutoff
    result["early_leave_flag"] = check_out_local < early_cutoff

    # Break time: sum of consecutive inter-sighting gaps > min_break_gap_minutes
    # NOTE: break_minutes is an estimate — gaps may include camera blind spots,
    # not just deliberate breaks. Interpret cautiously.
    min_break_gap = thresholds.get("min_break_gap_minutes", 10)
    break_total = 0.0
    for i in range(1, len(timestamps)):
        gap_minutes = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60.0
        if gap_minutes >= min_break_gap:
            break_total += gap_minutes
    result["break_minutes"] = round(break_total, 1)

    # Non-work zone time: estimate from sightings in non_work cameras
    non_work_sightings = [s for s in sightings if s.get("zone_type") == "non_work"]
    # Rough estimate: count of non_work sightings * sampling_interval_minutes
    # This is inherently imprecise — a proper estimate would need known intervals
    # For now: sum gaps between consecutive non_work sightings (same approach as breaks)
    if len(non_work_sightings) >= 2:
        nw_times = sorted([parse_ts(s["timestamp"]) for s in non_work_sightings])
        nw_total = 0.0
        for i in range(1, len(nw_times)):
            gap = (nw_times[i] - nw_times[i - 1]).total_seconds() / 60.0
            # Only count as continuous non-work time if gap < 30 min
            if gap < 30:
                nw_total += gap
        result["non_work_zone_minutes"] = round(nw_total, 1)

    return result


def run_aggregation(
    date_str: str,
    config: Dict[str, Any],
) -> int:
    """
    Run daily aggregation for all active employees on a given date.
    Returns the number of employees processed.
    """
    work_schedule = config.get("work_schedule", {})
    thresholds = config.get("thresholds", {})
    tz_str = work_schedule.get("timezone", "UTC")

    try:
        tz = pytz.timezone(tz_str)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning("Unknown timezone '%s', using UTC.", tz_str)
        tz = pytz.utc

    employees = db.get_all_employees(active_only=True)
    if not employees:
        logger.warning("No active employees found — nothing to aggregate.")
        return 0

    # Fetch all sightings for the date in one query
    all_sightings = db.get_sightings_for_date(date_str)

    # Group sightings by employee_id
    sightings_by_emp: Dict[str, List] = {}
    for s in all_sightings:
        eid = s["employee_id"]
        if eid not in sightings_by_emp:
            sightings_by_emp[eid] = []
        sightings_by_emp[eid].append(s)

    processed = 0
    for emp in employees:
        eid = emp["employee_id"]
        emp_sightings = sightings_by_emp.get(eid, [])
        record = compute_daily_attendance(
            eid, date_str, emp_sightings, work_schedule, thresholds, tz
        )
        db.upsert_daily_attendance(record)
        processed += 1
        logger.debug(
            "Aggregated %s for %s: status=%s, presence=%.0f min",
            eid, date_str, record["status"], record["presence_minutes"],
        )

    logger.info("Aggregation complete for %s: %d employees processed.", date_str, processed)
    return processed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--date", "start_date",
    default=None,
    help="Date to aggregate (YYYY-MM-DD). Defaults to today.",
)
@click.option(
    "--date-end",
    default=None,
    help="End date for a range aggregation (YYYY-MM-DD). Requires --date.",
)
@click.option("--config", "config_path", default="config.yaml")
@click.option("--verbose", is_flag=True)
def main(start_date, date_end, config_path, verbose):
    """Run daily attendance aggregation."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config = load_config(config_path)
    db_cfg = config.get("database", {})
    db.init_db(db_cfg.get("sqlite_path", "office_track.db"))

    today = date.today().isoformat()
    start = start_date or today

    if date_end:
        # Range aggregation
        current = date.fromisoformat(start)
        end = date.fromisoformat(date_end)
        dates = []
        while current <= end:
            dates.append(current.isoformat())
            current += timedelta(days=1)
    else:
        dates = [start]

    total = 0
    for d in dates:
        console.print(f"[bold]Aggregating:[/bold] {d}")
        n = run_aggregation(d, config)
        console.print(f"  [green][OK][/green] {n} employee(s) processed")
        total += n

    console.print(f"\n[bold green]Done.[/bold green] Total records updated: {total}")


if __name__ == "__main__":
    main()

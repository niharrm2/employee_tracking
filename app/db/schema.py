"""
app/db/schema.py — Database DDL and Migrations
================================================
Defines core schema and creates dynamic system_settings table.
"""
from __future__ import annotations
import logging
from app.db.connection import get_connection

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Enrolled employees with averaged ArcFace face embeddings
CREATE TABLE IF NOT EXISTS employees (
    employee_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    department    TEXT,
    embedding     BLOB NOT NULL,
    photo_path    TEXT,
    enrolled_at   TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1
);

-- Raw detection sightings (biometric face events)
CREATE TABLE IF NOT EXISTS sightings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id   TEXT REFERENCES employees(employee_id),
    camera_id     TEXT NOT NULL,
    zone          TEXT NOT NULL,
    zone_type     TEXT NOT NULL,
    confidence    REAL,
    event_type    TEXT NOT NULL,
    snapshot_path TEXT,
    timestamp     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sightings_employee_date ON sightings(employee_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sightings_timestamp ON sightings(timestamp);

-- Cell phone usage detection events
CREATE TABLE IF NOT EXISTS phone_detections (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id               TEXT NOT NULL,
    detected_near_employee_id TEXT REFERENCES employees(employee_id),
    confidence              REAL,
    snapshot_path           TEXT,
    timestamp               TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_phone_timestamp ON phone_detections(timestamp);

-- Fire and smoke hazard alerts
CREATE TABLE IF NOT EXISTS fire_smoke_alerts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id     TEXT NOT NULL,
    alert_type    TEXT NOT NULL,
    confidence    REAL,
    snapshot_path TEXT,
    timestamp     TEXT NOT NULL,
    acknowledged  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_fire_timestamp ON fire_smoke_alerts(timestamp);

-- Emotion telemetry readings
CREATE TABLE IF NOT EXISTS emotion_readings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id   TEXT REFERENCES employees(employee_id),
    camera_id     TEXT NOT NULL,
    emotion       TEXT NOT NULL,
    confidence    REAL,
    timestamp     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emotion_timestamp ON emotion_readings(timestamp);

-- Daily attendance rollup records
CREATE TABLE IF NOT EXISTS daily_attendance (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id            TEXT NOT NULL REFERENCES employees(employee_id),
    date                   TEXT NOT NULL,
    check_in               TEXT,
    check_out              TEXT,
    presence_minutes       REAL NOT NULL DEFAULT 0,
    status                 TEXT NOT NULL DEFAULT 'absent',
    late_flag              INTEGER NOT NULL DEFAULT 0,
    early_leave_flag       INTEGER NOT NULL DEFAULT 0,
    last_zone              TEXT,
    break_minutes          REAL NOT NULL DEFAULT 0,
    non_work_zone_minutes  REAL NOT NULL DEFAULT 0,
    computed_at            TEXT NOT NULL,
    UNIQUE(employee_id, date)
);
CREATE INDEX IF NOT EXISTS idx_daily_emp_date ON daily_attendance(employee_id, date);

-- API users for RBAC console
CREATE TABLE IF NOT EXISTS api_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'employee',
    employee_id   TEXT REFERENCES employees(employee_id),
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

-- Dynamic System Settings (RTSP vs Local Video mode, custom RTSP URLs, telemetry toggles)
CREATE TABLE IF NOT EXISTS system_settings (
    key           TEXT PRIMARY KEY,
    value         TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


def init_db(db_path: str = None) -> None:
    """Initialize database tables and run lightweight migrations."""
    if db_path:
        from app.db.connection import set_db_path
        set_db_path(db_path)
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        # Dynamic migration check
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(employees)").fetchall()]
        if "photo_path" not in cols:
            conn.execute("ALTER TABLE employees ADD COLUMN photo_path TEXT")
            logger.info("Migrated schema: added photo_path column to employees")
    logger.info("Database schema initialized and verified.")
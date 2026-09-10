"""
database.py — Compatibility Facade
====================================
Delegates all calls to the modern repository pattern under app.db.repositories.
Preserves 100% backward compatibility for existing tools, scripts, and legacy tests.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import numpy as np

from app.db.connection import get_connection, set_db_path, get_db_path
from app.db.schema import init_db
from app.db.repositories.employee_repo import (
    EmployeeRepository, embedding_to_blob, blob_to_embedding
)
from app.db.repositories.sighting_repo import SightingRepository
from app.db.repositories.attendance_repo import AttendanceRepository
from app.db.repositories.alert_repo import AlertRepository
from app.db.repositories.phone_repo import PhoneRepository
from app.db.repositories.emotion_repo import EmotionRepository

_emp_repo = EmployeeRepository()
_sighting_repo = SightingRepository()
_att_repo = AttendanceRepository()
_alert_repo = AlertRepository()
_phone_repo = PhoneRepository()
_emotion_repo = EmotionRepository()


def upsert_employee(employee_id: str, name: str, department: str, embedding: np.ndarray, photo_path: Optional[str] = None) -> None:
    _emp_repo.upsert(employee_id, name, department, embedding, photo_path)


def get_all_employees(active_only: bool = True) -> List[Dict[str, Any]]:
    return _emp_repo.get_all(active_only=active_only)


def get_employee(employee_id: str) -> Optional[Dict[str, Any]]:
    return _emp_repo.get_by_id(employee_id)


def deactivate_employee(employee_id: str) -> None:
    _emp_repo.deactivate(employee_id)


def insert_sighting(employee_id, camera_id, zone, zone_type, confidence, event_type, snapshot_path, timestamp) -> int:
    return _sighting_repo.insert(employee_id, camera_id, zone, zone_type, confidence, event_type, snapshot_path, timestamp)


def get_sightings_for_date(date_str: str, employee_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return _sighting_repo.get_by_date(date_str, employee_id)


def get_recent_sightings(minutes: int, zone_type: Optional[str] = None) -> List[Dict[str, Any]]:
    return _sighting_repo.get_recent(minutes, zone_type)


def get_unknown_face_sightings(limit: int = 100) -> List[Dict[str, Any]]:
    return _sighting_repo.get_unknown_faces(limit)


def insert_phone_detection(camera_id, detected_near_employee_id, confidence, snapshot_path, timestamp) -> int:
    return _phone_repo.insert(camera_id, detected_near_employee_id, confidence, snapshot_path, timestamp)


def get_phone_detections(date_str: str) -> List[Dict[str, Any]]:
    return _phone_repo.get_by_date(date_str)


def insert_fire_smoke_alert(camera_id, alert_type, confidence, snapshot_path, timestamp) -> int:
    return _alert_repo.insert(camera_id, alert_type, confidence, snapshot_path, timestamp)


def get_fire_smoke_alerts(acknowledged: Optional[bool] = None, limit: int = 100) -> List[Dict[str, Any]]:
    return _alert_repo.get_alerts(acknowledged, limit)


def acknowledge_alert(alert_id: int) -> None:
    _alert_repo.acknowledge(alert_id)


def insert_emotion_reading(employee_id, camera_id, emotion, confidence, timestamp) -> int:
    return _emotion_repo.insert(employee_id, camera_id, emotion, confidence, timestamp)


def upsert_daily_attendance(record: Dict[str, Any]) -> None:
    _att_repo.upsert(record)


def get_daily_attendance(date_str: str, employee_id: Optional[str] = None, department: Optional[str] = None) -> List[Dict[str, Any]]:
    return _att_repo.get_by_date(date_str, employee_id, department)


def get_attendance_range(start_date: str, end_date: str, employee_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return _att_repo.get_range(start_date, end_date, employee_id)


def create_api_user(username: str, hashed_password: str, role: str = "employee", employee_id: Optional[str] = None) -> None:
    _emp_repo.create_api_user(username, hashed_password, role, employee_id)


def get_api_user(username: str) -> Optional[Dict[str, Any]]:
    return _emp_repo.get_api_user(username)
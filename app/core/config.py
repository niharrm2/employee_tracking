# app/core/config.py — Typed Configuration
from __future__ import annotations
import os
from typing import List, Optional
import yaml

CONFIG_PATH = os.environ.get('OFFICE_TRACK_CONFIG', 'config.yaml')


class CameraConfig:
    __slots__ = ('id', 'name', 'rtsp_url', 'zone', 'zone_type', 'enabled')
    def __init__(self, **data):
        self.id = data['id']; self.name = data['name']
        self.rtsp_url = data.get('rtsp_url', '')
        self.zone = data.get('zone', self.id)
        self.zone_type = data.get('zone_type', 'work')
        self.enabled = data.get('enabled', True)
    def to_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}


class AppConfig:
    def __init__(self, path: str = CONFIG_PATH):
        with open(path, encoding='utf-8') as f:
            raw = yaml.safe_load(f)
        db = raw.get('database', {})
        self.db_path: str = db.get('sqlite_path', 'office_track.db')
        api = raw.get('api', {})
        self.api_host: str = api.get('host', '0.0.0.0')
        self.api_port: int = int(api.get('port', 8000))
        self.secret_key: str = api.get('secret_key', 'change-me')
        self.token_expiry_minutes: int = int(api.get('token_expiry_minutes', 480))
        self.default_admin_user: str = api.get('default_admin_user', 'admin')
        self.default_admin_password: str = api.get('default_admin_password', 'admin123')
        self.cameras: List[CameraConfig] = [
            CameraConfig(**c) for c in raw.get('cameras', []) if c.get('enabled', True)
        ]
        self.sampling: dict = raw.get('sampling', {})
        cap = raw.get('capture', {})
        self.capture_timeout: float = float(cap.get('timeout_seconds', 10))
        self.capture_retries: int = int(cap.get('max_retries', 2))
        self.capture_retry_delay: float = float(cap.get('retry_delay_seconds', 1.0))
        self.features: dict = raw.get('features', {})
        self.thresholds: dict = raw.get('thresholds', {})
        snap = raw.get('snapshots', {})
        self.snapshots_enabled: bool = bool(snap.get('enabled', True))
        self.snapshots_dir: str = snap.get('base_dir', 'snapshots')
        fr = raw.get('face_recognition', {})
        self.face_model_name: str = fr.get('model_name', 'buffalo_s')
        self.face_det_size: tuple = tuple(fr.get('det_size', [640, 640]))
        fs = raw.get('fire_smoke', {})
        self.fire_model_path: Optional[str] = fs.get('model_path')
        log = raw.get('logging', {})
        self.log_level: str = log.get('level', 'INFO')
        self.log_file: str = log.get('file', 'office_track.log')
        ws = raw.get('work_schedule', {})
        self.work_start: str = ws.get('start_time', '09:00')
        self.work_end: str = ws.get('end_time', '18:00')
        self.work_grace_minutes: int = int(ws.get('grace_period_minutes', 15))
        self.work_timezone: str = ws.get('timezone', 'Asia/Kolkata')

    def get_camera(self, camera_id: str) -> Optional[CameraConfig]:
        for c in self.cameras:
            if c.id == camera_id:
                return c
        return None


_cfg: Optional[AppConfig] = None

def get_config() -> AppConfig:
    global _cfg
    if _cfg is None:
        _cfg = AppConfig()
    return _cfg

def reset_config():
    global _cfg
    _cfg = None

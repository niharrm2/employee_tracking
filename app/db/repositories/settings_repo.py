"""
app/db/repositories/settings_repo.py — System Settings Repository
===================================================================
Manages persistent system configuration, specifically:
- camera_mode: "local" (play MP4 test files) vs "rtsp" (connect to live RTSP streams)
- camera_rtsp_urls: Map of camera_id -> RTSP stream URL
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.db.repositories.base import BaseRepository


class SettingsRepository(BaseRepository):

    def get(self, key: str, default: Any = None) -> Any:
        row = self._fetchone("SELECT value FROM system_settings WHERE key = ?", (key,))
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]

    def set(self, key: str, value: Any) -> None:
        val_str = json.dumps(value) if not isinstance(value, str) else value
        now = datetime.now(timezone.utc).isoformat()
        with self.connection as conn:
            conn.execute(
                """
                INSERT INTO system_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, val_str, now),
            )

    def get_all(self) -> Dict[str, Any]:
        rows = self._fetchall("SELECT key, value, updated_at FROM system_settings")
        result = {}
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value"])
            except Exception:
                result[r["key"]] = r["value"]
        return result

    def get_camera_mode(self) -> str:
        """Returns 'local' or 'rtsp' (defaults to 'local')."""
        mode = self.get("camera_mode", "local")
        return mode if mode in ("local", "rtsp") else "local"

    def set_camera_mode(self, mode: str) -> None:
        if mode not in ("local", "rtsp"):
            raise ValueError("Camera mode must be either 'local' or 'rtsp'")
        self.set("camera_mode", mode)

    def get_rtsp_urls(self) -> Dict[str, str]:
        """Returns dict of camera_id -> rtsp_url."""
        val = self.get("camera_rtsp_urls", {})
        return val if isinstance(val, dict) else {}

    def set_rtsp_urls(self, urls: Dict[str, str]) -> None:
        self.set("camera_rtsp_urls", urls)

    def update_single_rtsp_url(self, camera_id: str, url: str) -> None:
        urls = self.get_rtsp_urls()
        urls[camera_id] = url
        self.set_rtsp_urls(urls)
"""
app/services/alert_svc.py — Safety Hazard & Unknown Visitor Alerts Service
===========================================================================
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.db.repositories.alert_repo import AlertRepository
from app.db.repositories.sighting_repo import SightingRepository


class AlertService:
    def __init__(
        self,
        alert_repo: Optional[AlertRepository] = None,
        sighting_repo: Optional[SightingRepository] = None,
    ):
        self.alert_repo = alert_repo or AlertRepository()
        self.sighting_repo = sighting_repo or SightingRepository()

    def get_fire_smoke_alerts(self, acknowledged: Optional[bool] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self.alert_repo.get_alerts(acknowledged=acknowledged, limit=limit)

    def acknowledge_alert(self, alert_id: int) -> None:
        self.alert_repo.acknowledge(alert_id)

    def get_unknown_faces(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.sighting_repo.get_unknown_faces(limit=limit)
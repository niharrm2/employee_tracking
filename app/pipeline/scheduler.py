"""
app/pipeline/scheduler.py — Per-Camera, Per-Feature Interval Scheduler
========================================================================
Tracks last execution timestamps to enforce configurable minimum intervals
per camera without busy-waiting or thread bloat.
"""
from __future__ import annotations
import time
from typing import Dict, Tuple


class FeatureScheduler:
    def __init__(self, intervals: Dict[str, float]):
        self.intervals = intervals
        self._last_run: Dict[Tuple[str, str], float] = {}

    def is_due(self, camera_id: str, feature: str) -> bool:
        interval = self.intervals.get(feature, 30.0)
        key = (camera_id, feature)
        last = self._last_run.get(key, 0.0)
        return (time.monotonic() - last) >= interval

    def mark_executed(self, camera_id: str, feature: str) -> None:
        self._last_run[(camera_id, feature)] = time.monotonic()
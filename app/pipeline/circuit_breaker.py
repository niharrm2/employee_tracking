"""
app/pipeline/circuit_breaker.py — Fault Isolation Circuit Breaker
==================================================================
Protects detection pipeline from hanging when an RTSP camera stream drops or errors.
States:
  CLOSED    — Normal operation
  OPEN      — Camera failed consecutively; requests fail fast for cooldown_sec
  HALF_OPEN — Cooldown expired; single probe allowed to check recovery
"""
from __future__ import annotations
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


class CameraCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0):
        self.threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self._failures: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._state: Dict[str, str] = {}  # "CLOSED", "OPEN", "HALF_OPEN"

    def can_attempt(self, camera_id: str) -> bool:
        """Returns True if the camera is healthy or ready for a probe."""
        state = self._state.get(camera_id, "CLOSED")
        if state == "CLOSED":
            return True
        if state == "OPEN":
            last_fail = self._last_failure_time.get(camera_id, 0.0)
            if (time.monotonic() - last_fail) >= self.cooldown:
                self._state[camera_id] = "HALF_OPEN"
                logger.info("Circuit breaker for camera %s transitioned to HALF_OPEN (probing)", camera_id)
                return True
            return False
        if state == "HALF_OPEN":
            return True
        return True

    def record_success(self, camera_id: str) -> None:
        """Reset failure counter and close circuit."""
        if self._state.get(camera_id) != "CLOSED":
            logger.info("Camera %s recovered! Circuit breaker CLOSED.", camera_id)
        self._failures[camera_id] = 0
        self._state[camera_id] = "CLOSED"

    def record_failure(self, camera_id: str) -> None:
        """Increment failure counter; trip circuit if threshold exceeded."""
        fails = self._failures.get(camera_id, 0) + 1
        self._failures[camera_id] = fails
        self._last_failure_time[camera_id] = time.monotonic()

        if fails >= self.threshold:
            if self._state.get(camera_id) != "OPEN":
                logger.warning(
                    "Camera %s tripped circuit breaker (%d failures). State: OPEN (cooldown %ds)",
                    camera_id, fails, self.cooldown
                )
            self._state[camera_id] = "OPEN"
"""
app/core/exceptions.py — Custom Exception Hierarchy
=====================================================
All application-specific exceptions inherit from AppError so callers
can catch a single base type and get consistent error metadata.
"""
from typing import Optional


class AppError(Exception):
    """Base class for all VisionIQ application exceptions."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or message


# ── HTTP / Business logic errors ───────────────────────────────────────────

class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"


class AuthorizationError(AppError):
    status_code = 403
    error_code = "AUTHORIZATION_FAILED"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"


# ── Infrastructure errors ──────────────────────────────────────────────────

class DatabaseError(AppError):
    status_code = 503
    error_code = "DATABASE_ERROR"


class CameraConnectionError(AppError):
    status_code = 503
    error_code = "CAMERA_UNAVAILABLE"


class ConfigurationError(AppError):
    status_code = 500
    error_code = "CONFIGURATION_ERROR"


class DetectorError(AppError):
    status_code = 500
    error_code = "DETECTOR_ERROR"

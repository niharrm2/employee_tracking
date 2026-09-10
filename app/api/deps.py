"""
app/api/deps.py — Dependency Injection & Security Providers
============================================================
Provides injectable service instances and flexible authentication guards:
- Checks Authorization: Bearer <token>
- Checks query parameter ?token=
- Checks cookie access_token
- Allows seamless localhost fallback to default admin
"""
from __future__ import annotations
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_config
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import TokenData, decode_access_token
from app.db.repositories.settings_repo import SettingsRepository
from app.services.alert_svc import AlertService
from app.services.attendance_svc import AttendanceService
from app.services.camera_svc import CameraService
from app.services.employee_svc import EmployeeService
from app.services.export_svc import ExportService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# Service providers
def get_camera_service() -> CameraService:
    return CameraService()


def get_employee_service() -> EmployeeService:
    return EmployeeService()


def get_attendance_service() -> AttendanceService:
    return AttendanceService()


def get_alert_service() -> AlertService:
    return AlertService()


def get_export_service() -> ExportService:
    return ExportService()


def get_settings_repo() -> SettingsRepository:
    return SettingsRepository()


# Authentication & RBAC guards
async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
) -> TokenData:
    cfg = get_config()

    # 1. Bearer token in Authorization header
    raw_token = token

    # 2. Query param ?token=
    if not raw_token:
        raw_token = request.query_params.get("token")

    # 3. Cookie access_token
    if not raw_token:
        raw_token = request.cookies.get("access_token")

    # 4. If token found, decode it
    if raw_token:
        try:
            return decode_access_token(raw_token, cfg.secret_key)
        except AuthenticationError:
            pass

    # 5. Localhost / internal development fallback: allow default admin
    client_ip = request.client.host if request.client else ""
    if client_ip in ("127.0.0.1", "::1", "localhost", "testclient"):
        return TokenData(username="admin", role="admin", employee_id=None)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Please log in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*roles: str):
    """Dependency factory enforcing permitted user roles."""
    async def _guard(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(roles)}",
            )
        return current_user
    return _guard


require_admin = require_roles("admin")
require_admin_or_hr = require_roles("admin", "hr")
require_admin_hr_manager = require_roles("admin", "hr", "manager")
require_any_role = require_roles("admin", "hr", "manager", "employee")
"""
api/auth.py — JWT Authentication + Role-Based Access Control
=============================================================
Roles:
  admin    — full access to all endpoints
  hr       — attendance data, employee management, exports
  manager  — attendance data for their team, read-only employees
  employee — own attendance data only
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

import database as db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (injected from app startup — set these before first request)
# ---------------------------------------------------------------------------
_SECRET_KEY: str = "change-this-in-production"
_ALGORITHM: str = "HS256"
_TOKEN_EXPIRY_MINUTES: int = 480

import bcrypt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def configure_auth(secret_key: str, token_expiry_minutes: int = 480):
    global _SECRET_KEY, _TOKEN_EXPIRY_MINUTES
    _SECRET_KEY = secret_key
    _TOKEN_EXPIRY_MINUTES = token_expiry_minutes


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    employee_id: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=_TOKEN_EXPIRY_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = db.get_api_user(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return TokenData(
            username=username,
            role=payload.get("role"),
            employee_id=payload.get("employee_id"),
        )
    except JWTError:
        raise credentials_exception


# ---------------------------------------------------------------------------
# Role-based dependency factories
# ---------------------------------------------------------------------------

def require_roles(*roles: str):
    """Dependency factory: raises 403 if the current user's role isn't in roles."""
    async def _check(current_user: TokenData = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(roles)}",
            )
        return current_user
    return _check


# Convenience role dependencies
require_admin = require_roles("admin")
require_admin_or_hr = require_roles("admin", "hr")
require_admin_hr_manager = require_roles("admin", "hr", "manager")
require_any_role = require_roles("admin", "hr", "manager", "employee")

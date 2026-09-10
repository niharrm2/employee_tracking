"""
app/core/security.py — Cryptographic Security & RBAC Infrastructure
====================================================================
Implements bcrypt password hashing, HS256 JWT generation, and token claims verification.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel
from app.core.exceptions import AuthenticationError

_ALGORITHM = "HS256"


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    employee_id: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


def hash_password(plain_password: str) -> str:
    """Generate salted bcrypt password hash."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify raw password against bcrypt hash in constant time."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, secret_key: str, expiry_minutes: int = 480) -> str:
    """Encode JWT access token with expiration."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    payload["exp"] = expire
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> TokenData:
    """Verify and decode JWT access token into TokenData."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise AuthenticationError("Invalid token: missing subject identity")
        return TokenData(
            username=username,
            role=payload.get("role"),
            employee_id=payload.get("employee_id"),
        )
    except JWTError as exc:
        raise AuthenticationError(f"Session token verification failed: {exc}")
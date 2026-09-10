"""
app/api/v1/auth.py — Authentication Router
============================================
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_current_user, TokenData
from app.core.config import get_config
from app.core.security import Token, create_access_token, verify_password
from app.db.repositories.employee_repo import EmployeeRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    repo = EmployeeRepository()
    user = repo.get_api_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or security password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cfg = get_config()
    token = create_access_token(
        data={"sub": user["username"], "role": user["role"], "employee_id": user.get("employee_id")},
        secret_key=cfg.secret_key,
        expiry_minutes=cfg.token_expiry_minutes,
    )
    return Token(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        username=user["username"],
    )


@router.get("/me", response_model=TokenData)
async def get_me(current_user: TokenData = Depends(get_current_user)):
    return current_user
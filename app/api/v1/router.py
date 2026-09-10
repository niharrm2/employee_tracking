"""
app/api/v1/router.py — Root Aggregator for API v1
===================================================
"""
from __future__ import annotations
from fastapi import APIRouter

from app.api.v1.alerts import router as alerts_router
from app.api.v1.attendance import router as attendance_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cameras import router as cameras_router
from app.api.v1.employees import router as employees_router
from app.api.v1.exports import router as exports_router
from app.api.v1.live import router as live_router
from app.api.v1.settings import router as settings_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(cameras_router)
api_v1_router.include_router(attendance_router)
api_v1_router.include_router(employees_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(live_router)
api_v1_router.include_router(exports_router)
api_v1_router.include_router(settings_router)

# Backwards compatibility: also mount at /api (without /v1) for older dashboard code
legacy_api_router = APIRouter(prefix="/api")
legacy_api_router.include_router(auth_router)
legacy_api_router.include_router(cameras_router)
legacy_api_router.include_router(attendance_router)
legacy_api_router.include_router(employees_router)
legacy_api_router.include_router(alerts_router)
legacy_api_router.include_router(live_router)
legacy_api_router.include_router(exports_router)
legacy_api_router.include_router(settings_router)
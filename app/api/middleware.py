"""
app/api/middleware.py — Telemetry, Request Tracing & Exception Handling
========================================================================
"""
from __future__ import annotations
import time
import uuid
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("http")


class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        start_time = time.monotonic()

        response: Response
        try:
            response = await call_next(request)
        except AppError as app_err:
            logger.warning("[%s] Business error: %s (%s)", req_id, app_err.message, app_err.error_code)
            return JSONResponse(
                status_code=app_err.status_code,
                content={"error": app_err.error_code, "detail": app_err.message},
                headers={"X-Request-ID": req_id},
            )
        except Exception as exc:
            logger.error("[%s] Unhandled server error: %s", req_id, exc, exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "INTERNAL_SERVER_ERROR", "detail": "An internal server error occurred."},
                headers={"X-Request-ID": req_id},
            )

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        return response
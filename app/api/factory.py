"""
app/api/factory.py — Enterprise FastAPI Application Factory
============================================================
Builds and wires up the application with middleware, routers, template rendering,
and graceful lifespan management.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.middleware import TelemetryMiddleware
from app.api.v1.router import api_v1_router, legacy_api_router
from app.core.config import get_config
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.db.repositories.employee_repo import EmployeeRepository
from app.db.schema import init_db

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    setup_logging(level=cfg.log_level, log_file=cfg.log_file)
    logger.info("Initializing VisionIQ Enterprise API...")

    # Database initialization
    init_db(cfg.db_path)

    # Seed default administrator if not present
    emp_repo = EmployeeRepository()
    if emp_repo.get_api_user(cfg.default_admin_user) is None:
        hashed = hash_password(cfg.default_admin_password)
        emp_repo.create_api_user(cfg.default_admin_user, hashed, role="admin")
        logger.info("Default administrator '%s' initialized.", cfg.default_admin_user)

    yield
    logger.info("VisionIQ Enterprise API shutting down.")


def create_app() -> FastAPI:
    cfg = get_config()

    app = FastAPI(
        title="VisionIQ Enterprise Tracking & Surveillance System",
        description="CPU-optimized enterprise biometric presence, edge vision analytics, and hazard monitoring.",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(TelemetryMiddleware)

    # Static assets and template rendering
    base_dir = Path(__file__).parent.parent.parent
    app.mount(
        "/static",
        StaticFiles(directory=str(base_dir / "dashboard" / "static")),
        name="static",
    )
    templates = Jinja2Templates(directory=str(base_dir / "dashboard" / "templates"))

    # Include versioned and legacy API routers
    app.include_router(api_v1_router)
    app.include_router(legacy_api_router)

    # Server-rendered HTML dashboard pages
    @app.get("/", response_class=HTMLResponse)
    async def dashboard_home(request: Request):
        return templates.TemplateResponse(request=request, name="dashboard.html")

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        return templates.TemplateResponse(request=request, name="login.html")

    @app.get("/cameras", response_class=HTMLResponse)
    async def cameras_page(request: Request):
        return templates.TemplateResponse(request=request, name="cameras.html")

    @app.get("/attendance", response_class=HTMLResponse)
    async def attendance_page(request: Request):
        return templates.TemplateResponse(request=request, name="attendance.html")

    @app.get("/live", response_class=HTMLResponse)
    async def live_page(request: Request):
        return templates.TemplateResponse(request=request, name="live.html")

    @app.get("/alerts", response_class=HTMLResponse)
    async def alerts_page(request: Request):
        return templates.TemplateResponse(request=request, name="alerts.html")

    @app.get("/employees", response_class=HTMLResponse)
    async def employees_page(request: Request):
        return templates.TemplateResponse(request=request, name="employees.html")

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        return templates.TemplateResponse(request=request, name="settings.html")

    # Snapshot image serving
    @app.get("/snapshots/{file_path:path}")
    async def serve_snapshot(file_path: str):
        clean_path = file_path.replace("snapshots/", "").replace("snapshots\\", "")
        path = base_dir / cfg.snapshots_dir / clean_path
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Snapshot not found: {clean_path}")
        return FileResponse(str(path), media_type="image/jpeg")

    @app.get("/healthz", tags=["health"])
    async def health_check():
        return {"status": "HEALTHY", "service": "visioniq-api", "version": "2.0.0"}

    return app
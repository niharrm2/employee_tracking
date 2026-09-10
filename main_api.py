"""
main_api.py — Enterprise API Server Entry Point
=================================================
Usage:
    python main_api.py
    or:
    uvicorn main_api:app --host 0.0.0.0 --port 8000
"""
import uvicorn
from app.api.factory import create_app
from app.core.config import get_config

app = create_app()

if __name__ == "__main__":
    cfg = get_config()
    uvicorn.run(
        "main_api:app",
        host=cfg.api_host,
        port=cfg.api_port,
        reload=False,
        access_log=False,
    )
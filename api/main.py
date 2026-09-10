"""
api/main.py — Compatibility Application Factory Hook
=====================================================
Instantiates the enterprise FastAPI app from app.api.factory.
"""
from app.api.factory import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    from app.core.config import get_config
    cfg = get_config()
    uvicorn.run("api.main:app", host=cfg.api_host, port=cfg.api_port, reload=False)
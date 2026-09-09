"""App entrypoint. Run locally with: uvicorn app.main:app --reload (from backend/)."""

from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    get_settings()  # instantiated eagerly so a missing required env var fails fast, now

    app = FastAPI(title="PFMF Backend", version="0.1.0")
    app.include_router(health_router, prefix="/v1")
    return app


app = create_app()

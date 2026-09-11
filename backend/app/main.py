"""App entrypoint. Run locally with: uvicorn app.main:app --reload (from backend/)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.middleware import RequestIdMiddleware
from app.api.v1.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.health import router as health_router
from app.api.v1.me import router as me_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.transactions import scenario_transactions_router, transactions_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()  # instantiated eagerly so a missing required env var fails fast, now

    app = FastAPI(title="PFMF Backend", version="0.1.0")

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    app.include_router(health_router, prefix="/v1")
    app.include_router(auth_router, prefix="/v1")
    app.include_router(me_router, prefix="/v1")
    app.include_router(categories_router, prefix="/v1")
    app.include_router(scenarios_router, prefix="/v1")
    app.include_router(scenario_transactions_router, prefix="/v1")
    app.include_router(transactions_router, prefix="/v1")
    return app


app = create_app()

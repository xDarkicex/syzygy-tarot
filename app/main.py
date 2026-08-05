"""FastAPI app factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.storage.database import init_database
from app.web.routes import pages, readings as readings_routes, profile


def create_app() -> FastAPI:
    settings = get_settings()
    init_database(settings.database_path)

    app = FastAPI(title="syzygy-tarot", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    app.include_router(pages.router)
    app.include_router(readings_routes.router)
    app.include_router(profile.router)

    return app


app = create_app()

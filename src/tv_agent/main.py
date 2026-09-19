"""FastAPI application entry point."""

import uvicorn
from fastapi import FastAPI

from tv_agent import __version__
from tv_agent.api.router import api_router
from tv_agent.core.config import get_settings


def create_app() -> FastAPI:
    """Create an isolated app instance for production and tests."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.include_router(api_router)
    return app


app = create_app()


def run() -> None:
    """Run the development server through the installed console script."""
    settings = get_settings()
    uvicorn.run(
        "tv_agent.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )

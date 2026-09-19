"""FastAPI application composition and process entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src import __version__
from src.api import router
from src.config import Settings, get_settings
from src.douban import DoubanClient
from src.llm import DeepSeekPlanner
from src.resolver import MetadataResolver
from src.store import SQLiteResolutionStore


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        provider = DoubanClient(resolved_settings)
        planner = DeepSeekPlanner(resolved_settings) if resolved_settings.llm_configured else None
        store = SQLiteResolutionStore(resolved_settings.database_path)
        await store.initialize()
        app.state.resolver = MetadataResolver(resolved_settings, provider, store, planner)
        try:
            yield
        finally:
            await provider.close()
            if planner is not None:
                await planner.close()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        docs_url="/docs" if resolved_settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if resolved_settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()

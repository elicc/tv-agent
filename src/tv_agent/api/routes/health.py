"""Process health endpoint."""

from fastapi import APIRouter

from tv_agent import __version__
from tv_agent.core.config import get_settings
from tv_agent.schemas.health import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process health without exposing credentials."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        douban_configured=settings.douban_configured,
        llm_configured=settings.llm_configured,
    )

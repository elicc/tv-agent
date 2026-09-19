"""FastAPI routes and optional bearer authentication."""

import hmac
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src import __version__
from src.config import Settings
from src.models import HealthResponse, Metadata, ResolveRequest, ResolveResponse
from src.resolver import MetadataResolver

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def require_service_key(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    settings = _settings(request)
    if not settings.authentication_enabled:
        return
    expected = settings.service_api_key.get_secret_value() if settings.service_api_key else ""
    actual = (
        credentials.credentials
        if credentials and credentials.scheme.lower() == "bearer"
        else ""
    )
    if not actual or not hmac.compare_digest(expected, actual):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@router.get("/healthz", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = _settings(request)
    return HealthResponse(
        service=settings.app_name,
        version=__version__,
        douban_configured=settings.douban_configured,
        llm_configured=settings.llm_configured,
        authentication_enabled=settings.authentication_enabled,
    )


@router.post(
    "/api/v1/metadata/resolve",
    response_model=ResolveResponse,
    dependencies=[Depends(require_service_key)],
)
async def resolve_metadata(request: Request, payload: ResolveRequest) -> ResolveResponse:
    resolver = cast(MetadataResolver, request.app.state.resolver)
    return await resolver.resolve(payload)


@router.get(
    "/api/v1/metadata/douban/{external_id}",
    response_model=Metadata,
    dependencies=[Depends(require_service_key)],
)
async def douban_detail(
    request: Request,
    external_id: Annotated[str, Path(pattern=r"^\d+$", max_length=32)],
    external_type: Annotated[str, Query(pattern=r"^(movie|tv)$")] = "movie",
) -> Metadata:
    resolver = cast(MetadataResolver, request.app.state.resolver)
    return await resolver.detail(external_id, external_type)

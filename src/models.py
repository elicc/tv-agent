"""Provider-neutral HTTP and domain models."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class MovieIdentity(ApiModel):
    source_instance_id: str = Field(min_length=1, max_length=256)
    source_vod_id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=256)
    year: str = Field(default="", max_length=64)
    area: str = Field(default="", max_length=256)
    type: str = Field(default="", max_length=256)
    director: str = Field(default="", max_length=512)
    actors: str = Field(default="", max_length=1024)


class ResolveRequest(MovieIdentity):
    allow_agent: bool = True


class Artwork(ApiModel):
    url: str
    width: int = 0
    height: int = 0


class Metadata(ApiModel):
    provider: Literal["douban"] = "douban"
    external_id: str
    external_type: str = ""
    title: str = ""
    original_title: str = ""
    year: str = ""
    area: str = ""
    type: str = ""
    directors: str = ""
    actors: str = ""
    summary: str = ""
    poster: str = ""
    backdrop: str = ""
    backdrop_width: int = 0
    backdrop_height: int = 0
    rating: float = 0
    rating_count: int = 0
    duration: int = 0
    artworks: list[Artwork] = Field(default_factory=list)


class Candidate(ApiModel):
    metadata: Metadata
    deterministic_score: float = Field(default=0, ge=0, le=1)
    model_confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class ResolutionStatus(StrEnum):
    MATCHED = "matched"
    NEEDS_CONFIRMATION = "needs_confirmation"
    NOT_FOUND = "not_found"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class ResolutionMode(StrEnum):
    DETERMINISTIC = "deterministic"
    AGENT = "agent"
    CACHE = "cache"
    FALLBACK = "fallback"


class ResolveResponse(ApiModel):
    request_id: str
    status: ResolutionStatus
    mode: ResolutionMode
    selected: Metadata | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    message: str = ""


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    douban_configured: bool
    llm_configured: bool
    authentication_enabled: bool


class AgentAction(ApiModel):
    action: Literal["search", "fetch_detail", "select", "stop"]
    query: str = ""
    external_id: str = ""
    confidence: float = Field(default=0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    reason: str = ""

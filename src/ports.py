"""Application ports implemented by external adapters."""

from typing import Protocol

from src.models import AgentAction, Metadata, MovieIdentity, ResolveResponse


class MetadataProvider(Protocol):
    async def search(self, query: str, *, start: int = 0, count: int = 5) -> list[Metadata]: ...

    async def detail(self, external_id: str, external_type: str) -> Metadata: ...

    async def close(self) -> None: ...


class AgentPlanner(Protocol):
    async def decide(
        self,
        identity: MovieIdentity,
        candidates: list[Metadata],
        attempted_queries: list[str],
    ) -> AgentAction: ...

    async def close(self) -> None: ...


class ResolutionStore(Protocol):
    async def initialize(self) -> None: ...

    async def get(self, key: str) -> ResolveResponse | None: ...

    async def put(self, key: str, response: ResolveResponse, ttl_seconds: int) -> None: ...

from pathlib import Path

import pytest

from src.config import Settings
from src.models import (
    AgentAction,
    Metadata,
    MovieIdentity,
    ResolutionMode,
    ResolutionStatus,
    ResolveRequest,
)
from src.resolver import MetadataResolver
from src.store import SQLiteResolutionStore


class FakeProvider:
    def __init__(self) -> None:
        self.search_count = 0

    async def search(self, query: str, *, start: int = 0, count: int = 5) -> list[Metadata]:
        self.search_count += 1
        if query not in {"灵境行者", "Spirit Realm Walker"}:
            return []
        return [
            Metadata(
                external_id="36999847",
                external_type="tv",
                title="灵境行者",
                year="2023",
            )
        ]

    async def detail(self, external_id: str, external_type: str) -> Metadata:
        return Metadata(
            external_id=external_id,
            external_type=external_type,
            title="灵境行者",
            year="2023",
            type="剧情",
            directors="李泽露",
        )

    async def close(self) -> None:
        return None


class FakePlanner:
    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = actions

    async def decide(
        self,
        identity: MovieIdentity,
        candidates: list[Metadata],
        attempted_queries: list[str],
    ) -> AgentAction:
        return self.actions.pop(0)

    async def close(self) -> None:
        return None


def settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_path=path,
        douban_api_key="test",
        llm_api_key=None,
    )


@pytest.mark.asyncio
async def test_deterministic_match_is_cached(tmp_path: Path) -> None:
    provider = FakeProvider()
    store = SQLiteResolutionStore(tmp_path / "cache.db")
    await store.initialize()
    resolver = MetadataResolver(settings(tmp_path / "cache.db"), provider, store, None)
    request = ResolveRequest(
        source_instance_id="site",
        source_vod_id="1",
        title="灵境行者",
        year="2023",
    )

    first = await resolver.resolve(request)
    second = await resolver.resolve(request)

    assert first.status == ResolutionStatus.MATCHED
    assert second.mode == ResolutionMode.CACHE
    assert provider.search_count == 1


@pytest.mark.asyncio
async def test_agent_can_search_alias_but_only_select_returned_id(tmp_path: Path) -> None:
    provider = FakeProvider()
    planner = FakePlanner(
        [
            AgentAction(action="search", query="Spirit Realm Walker"),
            AgentAction(
                action="select",
                external_id="36999847",
                confidence=0.98,
                evidence=["年份一致", "别名一致"],
            ),
        ]
    )
    store = SQLiteResolutionStore(tmp_path / "agent.db")
    await store.initialize()
    resolver = MetadataResolver(settings(tmp_path / "agent.db"), provider, store, planner)

    result = await resolver.resolve(
        ResolveRequest(
            source_instance_id="site",
            source_vod_id="2",
            title="灵境行者国语版",
            year="2023",
            director="李泽露",
        )
    )

    assert result.status == ResolutionStatus.MATCHED
    assert result.mode == ResolutionMode.AGENT
    assert result.selected is not None
    assert result.selected.external_id == "36999847"

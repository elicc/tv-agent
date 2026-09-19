"""Deterministic-first metadata resolution with an optional bounded agent loop."""

import hashlib
import json
import logging
from collections.abc import Iterable
from uuid import uuid4

import httpx
from pydantic import ValidationError

from src import matcher
from src.config import Settings
from src.douban import DoubanUnavailable
from src.llm import AgentUnavailable
from src.models import (
    AgentAction,
    Candidate,
    Metadata,
    ResolutionMode,
    ResolutionStatus,
    ResolveRequest,
    ResolveResponse,
)
from src.ports import AgentPlanner, MetadataProvider, ResolutionStore

LOGGER = logging.getLogger(__name__)


class MetadataResolver:
    def __init__(
        self,
        settings: Settings,
        provider: MetadataProvider,
        store: ResolutionStore,
        planner: AgentPlanner | None,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._store = store
        self._planner = planner

    async def detail(self, external_id: str, external_type: str) -> Metadata:
        return await self._provider.detail(external_id, external_type)

    async def resolve(self, request: ResolveRequest) -> ResolveResponse:
        cache_key = _cache_key(request)
        cached = await self._store.get(cache_key)
        if cached is not None:
            return cached.model_copy(
                update={"request_id": str(uuid4()), "mode": ResolutionMode.CACHE}
            )

        try:
            response = await self._resolve_uncached(request)
        except (DoubanUnavailable, httpx.HTTPError) as error:
            LOGGER.warning("Douban unavailable for %s: %s", request.title, error)
            return self._response(
                ResolutionStatus.PROVIDER_UNAVAILABLE,
                ResolutionMode.FALLBACK,
                message="Douban provider unavailable",
            )

        if response.status != ResolutionStatus.PROVIDER_UNAVAILABLE:
            ttl = (
                self._settings.matched_cache_ttl_seconds
                if response.status == ResolutionStatus.MATCHED
                else self._settings.candidate_cache_ttl_seconds
            )
            await self._store.put(cache_key, response, ttl)
        return response

    async def _resolve_uncached(self, request: ResolveRequest) -> ResolveResponse:
        initial_query = matcher.query_title(request.title)
        attempted_queries = [initial_query]
        pool = _merge({}, await self._provider.search(initial_query))
        ranked = _rank(request, pool.values())
        if _can_auto_select(ranked):
            return await self._deterministic_match(request, ranked[0])

        if request.allow_agent and self._planner is not None:
            result = await self._agent_loop(request, pool, attempted_queries, tool_calls=1)
            if result is not None:
                return result

        ranked = _rank(request, pool.values())
        if ranked:
            return self._response(
                ResolutionStatus.NEEDS_CONFIRMATION,
                ResolutionMode.DETERMINISTIC,
                candidates=ranked,
                message="Candidate confirmation required",
            )
        return self._response(
            ResolutionStatus.NOT_FOUND,
            ResolutionMode.DETERMINISTIC,
            message="No Douban candidate found",
        )

    async def _deterministic_match(
        self, request: ResolveRequest, candidate: Candidate
    ) -> ResolveResponse:
        detail = await self._provider.detail(
            candidate.metadata.external_id,
            candidate.metadata.external_type,
        )
        score = matcher.score(request, detail)
        selected = Candidate(metadata=detail, deterministic_score=score)
        return self._response(
            ResolutionStatus.MATCHED,
            ResolutionMode.DETERMINISTIC,
            selected=detail,
            candidates=[selected],
            message="Automatically matched by deterministic policy",
        )

    async def _agent_loop(
        self,
        request: ResolveRequest,
        pool: dict[str, Metadata],
        attempted_queries: list[str],
        tool_calls: int,
    ) -> ResolveResponse | None:
        assert self._planner is not None
        details_loaded: set[str] = set()
        for _ in range(self._settings.agent_max_rounds):
            try:
                action = await self._planner.decide(
                    request,
                    list(pool.values()),
                    attempted_queries,
                )
            except (
                AgentUnavailable,
                ValidationError,
                ValueError,
                httpx.HTTPError,
                TimeoutError,
            ) as error:
                LOGGER.warning("Agent planner failed for %s: %s", request.title, error)
                return None

            if action.action == "search":
                query = _safe_query(action.query)
                if (
                    not query
                    or query in attempted_queries
                    or tool_calls >= self._settings.agent_max_tool_calls
                ):
                    continue
                attempted_queries.append(query)
                pool = _merge(pool, await self._provider.search(query, count=10))
                tool_calls += 1
                continue

            if action.action == "fetch_detail":
                external_id = action.external_id
                if (
                    external_id not in pool
                    or external_id in details_loaded
                    or tool_calls >= self._settings.agent_max_tool_calls
                ):
                    continue
                pool[external_id] = await self._provider.detail(
                    external_id,
                    pool[external_id].external_type,
                )
                details_loaded.add(external_id)
                tool_calls += 1
                continue

            if action.action == "select":
                return await self._agent_selection(
                    request, pool, action, details_loaded, tool_calls
                )

            if action.action == "stop":
                break
        return None

    async def _agent_selection(
        self,
        request: ResolveRequest,
        pool: dict[str, Metadata],
        action: AgentAction,
        details_loaded: set[str],
        tool_calls: int,
    ) -> ResolveResponse | None:
        selected = pool.get(action.external_id)
        if selected is None:
            return None
        if (
            selected.external_id not in details_loaded
            and tool_calls < self._settings.agent_max_tool_calls
        ):
            selected = await self._provider.detail(selected.external_id, selected.external_type)
            pool[selected.external_id] = selected
        deterministic_score = matcher.score(request, selected)
        candidate = Candidate(
            metadata=selected,
            deterministic_score=deterministic_score,
            model_confidence=action.confidence,
            evidence=action.evidence[:5],
        )
        safe_auto_match = (
            action.confidence >= 0.95
            and not matcher.hard_conflict(request, selected)
            and (
                deterministic_score >= matcher.CANDIDATE_THRESHOLD
                or matcher.corroboration_count(request, selected) >= 2
            )
        )
        ranked = _rank(request, pool.values())
        candidates = [candidate] + [
            item for item in ranked if item.metadata.external_id != selected.external_id
        ]
        if safe_auto_match:
            return self._response(
                ResolutionStatus.MATCHED,
                ResolutionMode.AGENT,
                selected=selected,
                candidates=candidates,
                message="Matched by bounded agent policy",
            )
        return self._response(
            ResolutionStatus.NEEDS_CONFIRMATION,
            ResolutionMode.AGENT,
            candidates=candidates,
            message="Agent candidate requires confirmation",
        )

    @staticmethod
    def _response(
        status: ResolutionStatus,
        mode: ResolutionMode,
        *,
        selected: Metadata | None = None,
        candidates: list[Candidate] | None = None,
        message: str = "",
    ) -> ResolveResponse:
        return ResolveResponse(
            request_id=str(uuid4()),
            status=status,
            mode=mode,
            selected=selected,
            candidates=candidates or [],
            message=message,
        )


def _merge(pool: dict[str, Metadata], items: list[Metadata]) -> dict[str, Metadata]:
    result = dict(pool)
    for item in items:
        if item.external_id:
            result[item.external_id] = item
    return result


def _rank(request: ResolveRequest, items: Iterable[Metadata]) -> list[Candidate]:
    metadata_items = list(items)
    candidates = [
        Candidate(metadata=item, deterministic_score=matcher.score(request, item))
        for item in metadata_items
        if isinstance(item, Metadata)
    ]
    candidates = [
        candidate
        for candidate in candidates
        if matcher.is_candidate(candidate.deterministic_score)
    ]
    return sorted(
        candidates,
        key=lambda candidate: candidate.deterministic_score,
        reverse=True,
    )[:10]


def _can_auto_select(candidates: list[Candidate]) -> bool:
    if not candidates:
        return False
    second = candidates[1].deterministic_score if len(candidates) > 1 else 0
    return matcher.is_automatic(candidates[0].deterministic_score, second)


def _safe_query(query: str) -> str:
    return " ".join((query or "").strip().split())[:80]


def _cache_key(request: ResolveRequest) -> str:
    payload = {
        "policyVersion": 1,
        "request": request.model_dump(mode="json", by_alias=True),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()

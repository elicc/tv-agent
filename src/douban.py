"""Asynchronous Douban provider adapter."""

from dataclasses import dataclass
from typing import Any

import httpx

from src.config import Settings
from src.models import Artwork, Metadata


class DoubanUnavailable(RuntimeError):
    pass


class DoubanClient:
    def __init__(self, settings: Settings) -> None:
        self._api_key = (
            settings.douban_api_key.get_secret_value() if settings.douban_api_key else ""
        )
        self._client = httpx.AsyncClient(
            base_url=settings.douban_base_url.rstrip("/"),
            timeout=settings.douban_timeout_seconds,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1_1) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
                    "MicroMessenger/8.0.46 NetType/WIFI Language/zh_CN"
                ),
                "Referer": "https://servicewechat.com/wx2f9b06c1de1ccfca",
                "Content-Type": "application/json",
            },
        )

    async def search(self, query: str, *, start: int = 0, count: int = 5) -> list[Metadata]:
        root = await self._request(
            "/api/v2/search/weixin",
            {"q": query, "start": str(start), "count": str(count)},
        )
        result: list[Metadata] = []
        for raw_item in _list(root, "items"):
            if not isinstance(raw_item, dict):
                continue
            item = raw_item
            target = _dict(item, "target")
            data = target or item
            external_type = _string(item, "target_type")
            if external_type not in {"movie", "tv"}:
                continue
            external_id = _string(item, "target_id") or _string(data, "id")
            if not external_id:
                continue
            rating = _dict(data, "rating")
            result.append(
                Metadata(
                    external_id=external_id,
                    external_type=external_type,
                    title=_string(data, "title"),
                    year=_string(data, "year"),
                    poster=_string(data, "cover_url")
                    or _nested_string(data, "pic", "normal", "nomal"),
                    rating=_number(rating, "value"),
                    rating_count=int(_number(rating, "count")),
                )
            )
        return result

    async def detail(self, external_id: str, external_type: str) -> Metadata:
        is_tv = external_type == "tv"
        path = f"/api/v2/{'tv' if is_tv else 'movie'}/{external_id}"
        root = await self._request(path, {})
        rating = _dict(root, "rating")
        metadata = Metadata(
            external_id=external_id,
            external_type="tv" if is_tv else "movie",
            title=_string(root, "title"),
            original_title=_string(root, "original_title"),
            year=_join_strings(_list(root, "pubdate")),
            area=_join_strings(_list(root, "countries")),
            type=_join_strings(_list(root, "genres")),
            directors=_join_names(_list(root, "directors")),
            actors=_join_names(_list(root, "actors")),
            summary=_string(root, "intro"),
            poster=_nested_string(root, "pic", "normal", "nomal")
            or _nested_string(root, "cover", "url"),
            rating=_number(rating, "value"),
            rating_count=int(_number(rating, "count")),
            duration=int(_number(root, "durations")),
        )
        try:
            await self._enrich_artwork(metadata)
        except (httpx.HTTPError, ValueError, DoubanUnavailable):
            pass
        return metadata

    async def close(self) -> None:
        await self._client.aclose()

    async def _enrich_artwork(self, metadata: Metadata) -> None:
        path = f"/api/v2/{metadata.external_type}/{metadata.external_id}/photos"
        root = await self._request(path, {"start": "0", "count": "20"})
        photos = _choose_photos(_list(root, "photos"))
        if not photos and _number(root, "total") > 20:
            root = await self._request(path, {"start": "20", "count": "20"})
            photos = _choose_photos(_list(root, "photos"))
        if not photos:
            return
        best = photos[0]
        metadata.backdrop = _artwork_url(best.url)
        metadata.backdrop_width = best.width
        metadata.backdrop_height = best.height
        metadata.artworks = [
            Artwork(url=_artwork_url(photo.url), width=photo.width, height=photo.height)
            for photo in photos
        ]

    async def _request(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        if not self._api_key:
            raise DoubanUnavailable("Douban API key is not configured")
        request_params = {**params, "apiKey": self._api_key}
        response = await self._client.get(path, params=request_params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Douban response is not an object")
        return payload


@dataclass(frozen=True)
class _Photo:
    url: str
    width: int
    height: int
    score: float


def _choose_photos(items: list[Any]) -> list[_Photo]:
    photos: list[_Photo] = []
    seen: set[str] = set()
    for raw_photo in items:
        if not isinstance(raw_photo, dict):
            continue
        image = _dict(raw_photo, "image")
        selected = _dict(image, "large") or _dict(image, "normal")
        url = _string(selected, "url") or _string(raw_photo, "url")
        width = int(_number(selected, "width"))
        height = int(_number(selected, "height"))
        if not url or url in seen or width < 800 or height < 450 or width < height:
            continue
        ratio = width / height
        if ratio < 1.45:
            continue
        seen.add(url)
        ratio_score = 1 - min(1, abs(ratio - 16 / 9) / 1.2)
        resolution_score = min(1, width * height / 2_000_000)
        photos.append(_Photo(url, width, height, ratio_score * 0.65 + resolution_score * 0.35))
    return sorted(photos, key=lambda photo: photo.score, reverse=True)[:10]


def _dict(value: dict[str, Any], key: str) -> dict[str, Any]:
    child = value.get(key)
    return child if isinstance(child, dict) else {}


def _list(value: dict[str, Any], key: str) -> list[Any]:
    child = value.get(key)
    return child if isinstance(child, list) else []


def _string(value: dict[str, Any], key: str) -> str:
    child = value.get(key)
    return str(child).strip() if child is not None else ""


def _nested_string(value: dict[str, Any], key: str, *names: str) -> str:
    child = _dict(value, key)
    return next((_string(child, name) for name in names if _string(child, name)), "")


def _number(value: dict[str, Any], key: str) -> float:
    try:
        return float(value.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _join_strings(items: list[Any]) -> str:
    return " / ".join(str(item).strip() for item in items if str(item).strip())


def _join_names(items: list[Any]) -> str:
    names = [_string(item, "name") for item in items if isinstance(item, dict)]
    return "、".join(name for name in names if name)


def _artwork_url(url: str) -> str:
    if "@Referer=" in url:
        return url
    return f"{url}@Referer=https://movie.douban.com/@User-Agent=Mozilla/5.0"

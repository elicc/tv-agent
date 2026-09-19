"""Small SQLite-backed resolution cache."""

import asyncio
import sqlite3
import time
from pathlib import Path

from src.models import ResolveResponse


class SQLiteResolutionStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def get(self, key: str) -> ResolveResponse | None:
        payload = await asyncio.to_thread(self._get_sync, key)
        return ResolveResponse.model_validate_json(payload) if payload else None

    async def put(self, key: str, response: ResolveResponse, ttl_seconds: int) -> None:
        await asyncio.to_thread(
            self._put_sync,
            key,
            response.model_dump_json(by_alias=True),
            int(time.time()) + ttl_seconds,
        )

    def _initialize_sync(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS resolution_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

    def _get_sync(self, key: str) -> str | None:
        now = int(time.time())
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload, expires_at FROM resolution_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            if int(row[1]) <= now:
                connection.execute("DELETE FROM resolution_cache WHERE cache_key = ?", (key,))
                return None
            return str(row[0])

    def _put_sync(self, key: str, payload: str, expires_at: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO resolution_cache(cache_key, payload, expires_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (key, payload, expires_at, int(time.time())),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=5)

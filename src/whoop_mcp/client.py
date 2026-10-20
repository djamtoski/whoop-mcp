"""Async WHOOP API v2 client with pagination, token refresh and rate-limit backoff."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

from . import config
from .auth import TokenManager

MAX_PAGE = 25


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class WhoopClient:
    def __init__(self, tokens: TokenManager | None = None, http: httpx.AsyncClient | None = None):
        self.tokens = tokens or TokenManager()
        self.http = http or httpx.AsyncClient(timeout=30)

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{config.API_BASE}{path}"
        refreshed = False
        for attempt in range(4):
            token = await self.tokens.access_token(self.http)
            resp = await self.http.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 401 and not refreshed:
                await self.tokens.access_token(self.http, force_refresh=True)
                refreshed = True
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                delay = float(resp.headers.get("Retry-After", 2 ** attempt))
                await asyncio.sleep(min(delay, 30))
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    async def _collection(self, path: str, start: datetime, end: datetime | None = None,
                          max_records: int = 200, page_delay: float = 0.0,
                          on_page: Any = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"start": _iso(start), "limit": MAX_PAGE}
        if end:
            params["end"] = _iso(end)
        records: list[dict[str, Any]] = []
        while True:
            page = await self._get(path, params)
            records.extend(page.get("records", []))
            if on_page:
                on_page(len(records))
            token = page.get("next_token") or page.get("nextToken")
            if not token or len(records) >= max_records:
                return records[:max_records]
            params["nextToken"] = token
            if page_delay:
                await asyncio.sleep(page_delay)

    async def history(self, path: str, start: datetime, on_page: Any = None) -> list[dict[str, Any]]:
        """Every record since `start`, throttled to stay under WHOOP's ~100 req/min limit."""
        return await self._collection(path, start, None, max_records=10**7, page_delay=0.7, on_page=on_page)

    # ---- endpoints
    async def cycles(self, start: datetime, end: datetime | None = None):
        return await self._collection("/v2/cycle", start, end)

    async def recoveries(self, start: datetime, end: datetime | None = None):
        return await self._collection("/v2/recovery", start, end)

    async def sleeps(self, start: datetime, end: datetime | None = None):
        return await self._collection("/v2/activity/sleep", start, end)

    async def workouts(self, start: datetime, end: datetime | None = None):
        return await self._collection("/v2/activity/workout", start, end)

    async def profile(self):
        return await self._get("/v2/user/profile/basic")

    async def body(self):
        return await self._get("/v2/user/measurement/body")

"""Fetch WHOOP records for a window and build the reports used by MCP tools and the dashboard."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import date, datetime, timedelta, timezone
from datetime import time as dtime
from typing import Any

from . import analytics as an
from . import demo
from .client import WhoopClient

CACHE_TTL_S = 120


class WhoopService:
    def __init__(self, demo_mode: bool | None = None, client: WhoopClient | None = None):
        if demo_mode is None:
            demo_mode = os.environ.get("WHOOP_MCP_DEMO", "").lower() in ("1", "true", "yes")
        self.demo_mode = demo_mode
        self._client = client
        self._cache: dict[tuple, tuple[float, dict[str, list]]] = {}
        self._lock = asyncio.Lock()

    @property
    def client(self) -> WhoopClient:
        if self._client is None:
            self._client = WhoopClient()
        return self._client

    async def raw(self, end_day: date, lookback_days: int) -> dict[str, list[dict[str, Any]]]:
        if self.demo_mode:
            return demo.generate(end=date.today(), days=max(lookback_days, 30))
        # Pad a day each side so timezone shifts don't drop edge records.
        start = datetime.combine(end_day - timedelta(days=lookback_days + 1), dtime.min, timezone.utc)
        end = datetime.combine(end_day + timedelta(days=2), dtime.min, timezone.utc)
        key = (start, end)
        async with self._lock:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
                return hit[1]
            cycles, recs, sleeps, workouts = await asyncio.gather(
                self.client.cycles(start, end), self.client.recoveries(start, end),
                self.client.sleeps(start, end), self.client.workouts(start, end),
            )
            data = {"cycles": cycles, "recoveries": recs, "sleeps": sleeps, "workouts": workouts}
            self._cache[key] = (time.monotonic(), data)
            return data

    async def _table(self, day: date, lookback: int):
        raw = await self.raw(day, lookback)
        return raw, an.daily_table(raw["cycles"], raw["recoveries"], raw["sleeps"], raw["workouts"])

    # ---- reports
    async def recovery(self, day_str: str | None) -> dict[str, Any]:
        day = an.parse_day(day_str)
        _, table = await self._table(day, 8)
        rep = an.recovery_report(table, day)
        if not rep["available"] and day == date.today():
            prev = an.recovery_report(table, day - timedelta(days=1))
            if prev["available"]:
                return {**prev, "stale": True,
                        "note": "Today's recovery isn't scored yet (no sleep since); showing the latest."}
        return rep

    async def strain(self, days_back: int) -> dict[str, Any]:
        days_back = max(1, min(int(days_back), 30))
        day = date.today()
        _, table = await self._table(day, days_back + 1)
        return an.strain_report(table, day, days_back)

    async def sleep(self, day_str: str | None) -> dict[str, Any]:
        day = an.parse_day(day_str)
        raw, table = await self._table(day, 8)
        rep = an.sleep_report(table, raw["sleeps"], day)
        if not rep["available"] and day == date.today():
            prev = an.sleep_report(table, raw["sleeps"], day - timedelta(days=1))
            if prev["available"]:
                return {**prev, "stale": True, "note": "No sleep ending today yet; showing last night's."}
        return rep

    async def trends(self) -> dict[str, Any]:
        day = date.today()
        _, table = await self._table(day, 28)
        return an.weekly_trends(table, day)

    async def recent_context(self, lookback: int = 28) -> dict[str, Any]:
        """Recent recovery by day and every WHOOP workout (summarised), for the strength log and the plan."""
        day = date.today()
        _, table = await self._table(day, lookback)
        recovery = {str(d): v for d, row in table.items() if (v := an._vitals(row)["recovery"]) is not None}
        workouts = [an.summarize_workout(w) for row in table.values() for w in row["workouts"]]
        return {"recovery": recovery, "workouts": workouts}

    async def summary(self) -> dict[str, Any]:
        """Everything the dashboard needs in one round-trip (one 28-day fetch)."""
        day = date.today()
        raw, table = await self._table(day, 28)
        rec = an.recovery_report(table, day)
        if not rec["available"]:  # before today's recovery is scored, show yesterday's
            prev = an.recovery_report(table, day - timedelta(days=1))
            if prev["available"]:
                rec = {**prev, "stale": True}
        sleep = an.sleep_report(table, raw["sleeps"], day)
        if not sleep["available"]:
            prev_sleep = an.sleep_report(table, raw["sleeps"], day - timedelta(days=1))
            if prev_sleep["available"]:
                sleep = {**prev_sleep, "stale": True}
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "demo": self.demo_mode,
            "recovery": rec,
            "sleep": sleep,
            "strain": an.strain_report(table, day, 7),
            "workout_days": an.strain_report(table, day, 28)["days"],
            "trends": an.weekly_trends(table, day),
        }

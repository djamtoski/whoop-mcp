"""Strength and plan overviews shared by the dashboard API and the MCP tools.

Both join local data (strength log, plan settings) with WHOOP data: the full-history export
overlaid with the live recent window. Without live data (offline, not logged in) the export
alone is used.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from . import plan, program, strength
from . import strength_analytics as sa
from .history import build_history
from .service import WhoopService

log = logging.getLogger("whoop_mcp.views")
WORKOUT_FIELDS = ("id", "date", "start", "timezone_offset", "sport", "discipline", "duration_min", "strain", "avg_hr", "max_hr")


async def _context(svc: WhoopService, lookback: int) -> dict[str, Any]:
    hist = await asyncio.to_thread(build_history)
    recovery = {d["date"]: d["recovery"] for d in hist.get("days", []) if d.get("recovery") is not None}
    workouts = {w["id"]: {"id": w["id"], "date": w["date"], "start": w["start"], "timezone_offset": w.get("timezone_offset"),
                          "sport": w["sport"], "discipline": w["discipline"], "duration_min": w["minutes"],
                          "strain": w["strain"], "avg_hr": w["avg_hr"], "max_hr": w["max_hr"]}
                for w in hist.get("workouts", [])}
    live_ok = True
    try:
        live = await svc.recent_context(lookback)
        recovery.update(live["recovery"])
        workouts.update({w["id"]: {k: w.get(k) for k in WORKOUT_FIELDS} for w in live["workouts"]})
    except Exception:  # noqa: BLE001 - offline or not logged in: the export alone still works
        live_ok = False
        log.info("live WHOOP context unavailable", exc_info=True)
    return {"recovery": recovery, "body_kg": (hist.get("body") or {}).get("weight_kilogram"), "body": hist.get("body") or {},
            "workouts": sorted(workouts.values(), key=lambda w: w["start"] or "", reverse=True), "live": live_ok}


async def strength_overview(svc: WhoopService) -> dict[str, Any]:
    ctx = await _context(svc, 28)
    sessions, exercises = await asyncio.gather(asyncio.to_thread(strength.list_sessions),
                                               asyncio.to_thread(strength.list_exercises))
    linked = {s["whoop_workout_id"] for s in sessions if s["whoop_workout_id"]}
    whoop = [w for w in ctx["workouts"] if w["discipline"] == "strength"]
    return {
        **sa.summary(sessions, exercises, ctx["recovery"], ctx["body_kg"]),
        "body_kg": ctx["body_kg"],
        "whoop_sessions": [{**w, "logged": w["id"] in linked} for w in whoop[:60]],
    }


async def plan_overview(svc: WhoopService, today: date | None = None) -> dict[str, Any]:
    ctx = await _context(svc, 14)
    today = today or date.today()
    settings = await asyncio.to_thread(plan.load_settings)
    habits = plan.habits(ctx["workouts"])
    psettings = await asyncio.to_thread(program.load_settings)
    pweek = next((w for w in program.build(psettings, ctx["body"])["weeks"] if w["startDate"] <= str(today) <= w["endDate"]), None)
    week = plan.from_program(pweek, habits, psettings["race_date"], today) if pweek else plan.build_week(settings, habits, today)
    plan.mark_done(week, ctx["workouts"])
    rec_today = ctx["recovery"].get(str(today))
    for day in week["days"]:
        if day["date"] == str(today):
            for s in day["sessions"]:
                s["adjustment"] = plan.adjust_for_recovery(s, rec_today)
    return {"settings": settings, "habits": habits, "week": week, "today": str(today),
            "recovery_today": rec_today, "live": ctx["live"]}


async def find_whoop_strength_workout(svc: WhoopService, day: str) -> dict[str, Any] | None:
    """The longest WHOOP strength workout on `day`, if any (to link a session logged in chat)."""
    ctx = await _context(svc, 28)
    same_day = [w for w in ctx["workouts"] if w["discipline"] == "strength" and w["date"] == day]
    return max(same_day, key=lambda w: w["duration_min"] or 0, default=None)


async def program_overview(svc: WhoopService, today: date | None = None) -> dict[str, Any]:
    """The whole season program with done ticks, today's recovery adjustment and kg for every lift."""
    ctx = await _context(svc, 28)
    today = today or date.today()
    settings = await asyncio.to_thread(program.load_settings)
    sessions, exercises = await asyncio.gather(asyncio.to_thread(strength.list_sessions),
                                               asyncio.to_thread(strength.list_exercises))
    prog = program.build(settings, ctx["body"])
    program.mark_done(prog, ctx["workouts"], {s["date"] for s in sessions}, today)
    maxes = program.estimated_maxes(sessions, exercises, ctx["body_kg"], today)
    ids = {e["name"].lower(): e["id"] for e in exercises}
    rec_today = ctx["recovery"].get(str(today))
    current = None
    for week in prog["weeks"]:
        program.fill_loads(week, maxes, ids, ctx["body_kg"])
        if week["startDate"] <= str(today) <= week["endDate"]:
            current = week["weekNumber"]
            for day in week["days"]:
                if day["date"] == str(today):
                    for w in day["workouts"]:
                        if w["sport"] in ("swim", "bike", "run", "strength"):
                            w["adjustment"] = plan.adjust_for_recovery({"sport": w["sport"], "kind": w["type"]}, rec_today)
    return {"settings": settings, "program": prog, "today": str(today), "current_week": current,
            "recovery_today": rec_today, "maxes": maxes, "body_kg": ctx["body_kg"], "live": ctx["live"]}

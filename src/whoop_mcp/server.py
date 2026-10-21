"""FastMCP server exposing WHOOP triathlon-coaching tools."""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import FastMCP

from . import config, insights
from .auth import AuthError
from .service import WhoopService

mcp = FastMCP(
    "whoop",
    instructions=(
        "WHOOP physiology for a triathlete. Use the get_whoop_* tools to read recovery, strain, "
        "sleep and trends, then call update_dashboard_insights with concise markdown coaching "
        "guidance. Fields marked derived=true (stress_estimate, target_strain, rolling sleep debt) "
        "are computed heuristics, not native WHOOP metrics. "
        "Lifts (sets, reps, kg) are not in WHOOP's API: log them with log_strength_session and read "
        "them with get_strength_progress. get_training_plan returns this week's 70.3 plan adjusted "
        "for today's recovery; update_training_plan changes race date, hours and training days. "
        f"Dashboard: http://localhost:{config.PORT}"
    ),
)
service = WhoopService()


async def _safe(coro) -> dict[str, Any]:
    try:
        return await coro
    except AuthError as e:
        return {"error": str(e), "fix": "Run `python -m whoop_mcp login` in the project directory."}
    except ValueError as e:
        return {"error": f"Invalid argument: {e}. Dates use YYYY-MM-DD, 'today' or 'yesterday'."}
    except Exception as e:  # noqa: BLE001 - surface API failures to the model, never crash the server
        return {"error": f"{type(e).__name__}: {e}"}


@mcp.tool
async def get_whoop_recovery(date: str = "today") -> dict[str, Any]:
    """Recovery for a day: recovery score (0-100%), readiness zone, HRV (rmssd ms) vs 7-day
    baseline, resting HR, SpO2, skin temp + deviation, respiratory rate, an estimated stress
    score (0-3) and a heuristic target day-strain band.

    Args:
        date: YYYY-MM-DD, "today" or "yesterday" (local date of waking).
    """
    return await _safe(service.recovery(date))


@mcp.tool
async def get_whoop_strain_and_activities(days_back: int = 7) -> dict[str, Any]:
    """Day strain (0-21) per day plus logged workouts classified as swim/bike/run/tri/strength/other,
    each with duration, strain, avg/max HR, kilojoules, distance and HR-zone minutes (z0-z5).
    Also returns per-discipline volume totals for the window.

    Args:
        days_back: number of days including today (1-30).
    """
    return await _safe(service.strain(days_back))


@mcp.tool
async def get_whoop_sleep_and_debt(date: str = "today") -> dict[str, Any]:
    """Main sleep ending on `date`: performance %, hours needed vs slept (with need breakdown),
    efficiency %, consistency %, awakenings, stages (deep/SWS, REM, light, awake), naps, and
    sleep-debt calculations (WHOOP debt component, tonight's shortfall, rolling 7-day debt).

    Args:
        date: YYYY-MM-DD, "today" or "yesterday" (local date the sleep ended).
    """
    return await _safe(service.sleep(date))


@mcp.tool
async def get_whoop_weekly_trends() -> dict[str, Any]:
    """Last 7 days of recovery, HRV, RHR, strain and sleep vs a 28-day baseline, including trend
    direction, acute:chronic strain ratio and overtraining warning flags."""
    return await _safe(service.trends())


@mcp.tool
async def get_whoop_full_history(refresh: bool = False) -> dict[str, Any]:
    """Your entire WHOOP history summarised by month: average recovery, HRV, RHR, day strain,
    sleep hours/performance and training volume per discipline (sessions, hours, km). Use for
    season-level, block-to-block or year-over-year analysis.

    Reads the latest full export; pulls a fresh one from WHOOP if none exists or refresh=True
    (a full export can take a few minutes because of API rate limits). Raw JSON/CSV files are
    written to the export directory returned here.

    Args:
        refresh: re-download the full history from WHOOP first.
    """
    import json

    from .export import export_history, latest_export

    async def run():
        path = latest_export()
        if path and not refresh and (path / "manifest.json").exists():
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        else:
            manifest = await export_history()
        manifest.pop("files", None)
        return manifest

    return await _safe(run())


@mcp.tool
async def update_dashboard_insights(markdown_text: str, title: str = "") -> dict[str, Any]:
    """Publish coaching guidance (markdown) to the live dashboard's AI Coaching Feed.

    Args:
        markdown_text: the coaching note. Headings, lists, bold and tables are supported.
        title: optional short headline for the card.
    """
    try:
        item = insights.add_insight(markdown_text, title or None)
    except ValueError as e:
        return {"error": str(e)}
    return {"ok": True, "id": item["id"], "dashboard_url": f"http://localhost:{config.PORT}"}


# --------------------------------------------------------------------------- strength log + plan

@mcp.tool
async def log_strength_session(sets: list[dict[str, Any]], date: str = "today", notes: str = "",
                               link_whoop: bool = True) -> dict[str, Any]:
    """Log a strength session's sets (WHOOP's API has no exercise data, so lifts live in this log).

    Args:
        sets: one entry per set, in order, e.g. {"exercise": "Back Squat", "reps": 5, "weight_kg": 100,
            "rpe": 8, "warmup": false}. Exercise names match the library case-insensitively (see
            get_strength_progress for the list); for bodyweight lifts weight_kg is the added load.
        date: YYYY-MM-DD, 'today' or 'yesterday'.
        notes: optional free text.
        link_whoop: attach the session to that day's WHOOP strength workout (strain, HR) if there is one.
    """
    from . import analytics as an
    from . import strength, views

    async def run():
        day = str(an.parse_day(date))
        whoop = await views.find_whoop_strength_workout(service, day) if link_whoop else None
        saved = await asyncio.to_thread(strength.save_session, day, sets, notes, whoop["id"] if whoop else None)
        return {"ok": True, "session": saved, "linked_whoop_workout": whoop,
                "dashboard_url": f"http://localhost:{config.PORT}/#strength"}

    return await _safe(run())


@mcp.tool
async def get_strength_progress(exercise: str = "") -> dict[str, Any]:
    """Strength progress from the log: per-exercise estimated 1RM, PRs and 4-week change, weekly sets
    per muscle with push/pull and lower/upper balance, performance by morning recovery zone, the
    exercise library, and WHOOP strength workouts that have no sets logged yet.

    Args:
        exercise: optional name to return only that lift's full session history.
    """
    from . import strength, views

    async def run():
        ov = await views.strength_overview(service)
        if exercise:
            match = [p for p in ov["progress"] if p["name"].lower() == exercise.strip().lower()]
            if not match:
                return {"error": f"No logged sessions for {exercise!r}.", "logged": [p["name"] for p in ov["progress"]]}
            return match[0]
        for p in ov["progress"]:
            p["points"] = p["points"][-5:]  # keep the reply short; ask for one exercise for its full history
        ov["balance"]["weeks"] = ov["balance"]["weeks"][-4:]
        ov["recovery"]["sessions"] = ov["recovery"]["sessions"][:10]
        ov["unlogged_whoop_sessions"] = [w for w in ov.pop("whoop_sessions") if not w["logged"]][:10]
        ov["library"] = [e["name"] for e in await asyncio.to_thread(strength.list_exercises)]
        return ov

    return await _safe(run())


@mcp.tool
async def get_training_plan() -> dict[str, Any]:
    """This week's Half Ironman (70.3) plan: phase and weeks to race, each day's sessions (sport, minutes,
    zone, description), what is already done according to WHOOP, today's recovery adjustment, and the
    athlete's usual weekly pattern the plan is built on."""
    from . import views

    return await _safe(views.plan_overview(service))


@mcp.tool
async def update_training_plan(race_date: str | None = None, race_name: str | None = None,
                               weekly_hours: float | None = None, strength_days: list[int] | None = None,
                               long_ride_day: int | None = None, long_run_day: int | None = None,
                               rest_day: int | None = None) -> dict[str, Any]:
    """Change plan settings; only the arguments you pass change. Days are 0 (Mon) to 6 (Sun).

    Args:
        race_date: YYYY-MM-DD, or "" to clear it (the plan then stays in base).
        race_name: e.g. "Ironman 70.3 Zell am See".
        weekly_hours: total training hours per week, 3-25.
        strength_days: up to 3 gym weekdays, e.g. [0, 3].
        long_ride_day / long_run_day / rest_day: weekday numbers, all different.
    """
    from . import plan

    patch = {k: v for k, v in {"race_date": race_date, "race_name": race_name, "weekly_hours": weekly_hours,
                               "strength_days": strength_days, "long_ride_day": long_ride_day,
                               "long_run_day": long_run_day, "rest_day": rest_day}.items() if v is not None}
    if patch.get("race_date") == "":
        patch["race_date"] = None
    try:
        return {"ok": True, "settings": await asyncio.to_thread(plan.save_settings, patch)}
    except (ValueError, TypeError) as e:
        return {"error": str(e)}

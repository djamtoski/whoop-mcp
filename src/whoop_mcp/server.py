"""FastMCP server exposing WHOOP triathlon-coaching tools."""

from __future__ import annotations

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

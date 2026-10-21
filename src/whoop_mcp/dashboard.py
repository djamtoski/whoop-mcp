"""FastAPI backend serving the dashboard SPA and its JSON/SSE API."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import config, insights, strength, views
from .auth import AuthError, complete_pending_login, load_tokens
from .service import WhoopService

log = logging.getLogger("whoop_mcp.dashboard")

app = FastAPI(title="WHOOP Triathlon Dashboard", docs_url=None, redoc_url=None)
# The API now writes (strength log), so only answer requests addressed to this machine (blocks DNS rebinding).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
_live = WhoopService()
_demo = WhoopService(demo_mode=True)


@app.get("/api/status")
async def status():
    return {"logged_in": load_tokens() is not None, "demo_env": _live.demo_mode}


@app.get("/api/summary")
async def summary(demo: bool = Query(False)):
    svc = _demo if demo else _live
    try:
        return await svc.summary()
    except AuthError as e:
        return JSONResponse({"error": "not_logged_in", "detail": str(e)}, status_code=401)
    except Exception as e:  # noqa: BLE001
        log.exception("summary failed")
        return JSONResponse({"error": "whoop_error", "detail": f"{type(e).__name__}: {e}"}, status_code=502)


@app.get("/api/history")
async def history():
    from .history import build_history

    return await asyncio.to_thread(build_history)


class SetIn(BaseModel):
    exercise_id: int
    reps: int
    weight_kg: float = 0
    rpe: float | None = None
    warmup: bool = False


class SessionIn(BaseModel):
    date: str
    sets: list[SetIn]
    notes: str = ""
    whoop_workout_id: str | None = None


class ExerciseIn(BaseModel):
    name: str
    pattern: str
    muscles: list[str]
    push_pull: str = "none"
    region: str | None = None
    bodyweight: bool = False


def _bad(problem: str) -> JSONResponse:
    # Validation messages come from the check_* functions' return values, never from exception text.
    return JSONResponse({"error": "invalid", "detail": problem}, status_code=400)


async def _save(fn, *args):
    """Run a write that its check_* function already accepted."""
    try:
        return await asyncio.to_thread(fn, *args)
    except ValueError:  # raced with another writer between the check and the write
        log.warning("write rejected after validation", exc_info=True)
        return _bad("Could not save; reload and try again.")


@app.get("/api/strength/exercises")
async def strength_exercises():
    return await asyncio.to_thread(strength.list_exercises)


@app.post("/api/strength/exercises")
async def strength_add_exercise(body: ExerciseIn):
    args = [body.name, body.pattern, body.muscles, body.push_pull, body.region, body.bodyweight]
    if problem := await asyncio.to_thread(strength.check_exercise, *args):
        return _bad(problem)
    return await _save(strength.add_exercise, *args)


@app.get("/api/strength/sessions")
async def strength_sessions(since: str | None = None):
    return await asyncio.to_thread(strength.list_sessions, since)


@app.post("/api/strength/sessions")
async def strength_create(body: SessionIn):
    sets = [s.model_dump() for s in body.sets]
    if problem := await asyncio.to_thread(strength.check_session, body.date, sets):
        return _bad(problem)
    return await _save(strength.save_session, body.date, sets, body.notes, body.whoop_workout_id)


@app.put("/api/strength/sessions/{session_id}")
async def strength_update(session_id: int, body: SessionIn):
    sets = [s.model_dump() for s in body.sets]
    if problem := await asyncio.to_thread(strength.check_session, body.date, sets, session_id):
        return _bad(problem)
    return await _save(strength.save_session, body.date, sets, body.notes, body.whoop_workout_id, session_id)


@app.delete("/api/strength/sessions/{session_id}")
async def strength_delete(session_id: int):
    if not await asyncio.to_thread(strength.delete_session, session_id):
        return JSONResponse({"error": "not_found", "detail": f"No session {session_id}."}, status_code=404)
    return {"deleted": session_id}


@app.get("/api/strength/summary")
async def strength_summary(demo: bool = Query(False)):
    return await views.strength_overview(_demo if demo else _live)


class PlanSettingsIn(BaseModel):
    race_name: str | None = None
    race_date: str | None = None
    weekly_hours: float | None = None
    strength_days: list[int] | None = None
    long_ride_day: int | None = None
    long_run_day: int | None = None
    rest_day: int | None = None


@app.get("/api/plan")
async def plan_week(demo: bool = Query(False)):
    return await views.plan_overview(_demo if demo else _live)


@app.put("/api/plan/settings")
async def plan_settings(body: PlanSettingsIn):
    from . import plan

    patch = body.model_dump(exclude_unset=True)
    if problem := await asyncio.to_thread(plan.check_settings, patch):
        return _bad(problem)
    return await _save(plan.save_settings, patch)


@app.get("/api/insights")
async def get_insights():
    return insights.list_insights()


@app.get("/api/events")
async def events():
    """Server-sent events: emits the insight list whenever the store file changes."""

    async def stream():
        last = None
        tick = 0
        while True:
            v = insights.version()
            if v != last:
                last = v
                yield f"event: insights\ndata: {json.dumps(insights.list_insights())}\n\n"
            elif tick % 15 == 0:
                yield ": keep-alive\n\n"
            tick += 1
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/callback")
async def callback(request: Request):
    """OAuth redirect target when the dashboard owns the port during `python -m whoop_mcp login`."""
    query: dict[str, list[str]] = {}
    for k, v in request.query_params.multi_items():
        query.setdefault(k, []).append(v)
    status, html = await asyncio.to_thread(complete_pending_login, query)
    return HTMLResponse(html, status_code=status)


if (config.STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")


@app.get("/{path:path}")
async def spa(path: str):
    # An unknown API path must not fall through to the page: the client would try to parse HTML as JSON.
    if path == "api" or path.startswith("api/"):
        return JSONResponse({"error": "not_found", "detail": f"No API endpoint /{path}."}, status_code=404)
    index = config.STATIC_DIR / "index.html"
    candidate = (config.STATIC_DIR / path).resolve()
    if path and candidate.is_file() and config.STATIC_DIR.resolve() in candidate.parents:
        return FileResponse(candidate)
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<h1>Dashboard not built</h1><p>Run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>.</p>",
        status_code=503,
    )


def port_free(host: str = config.HOST, port: int = config.PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0


def run(host: str = config.HOST, port: int = config.PORT) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_reloading_subprocess() -> bool:
    """Start `dashboard --reload` as a child process if the port is free (used by the MCP server).

    The dashboard then picks up Python changes on its own, without restarting the MCP server.
    The child exits when this process does. Returns False if something already owns the port.
    """
    if not port_free():
        return False
    import atexit
    import os
    import subprocess
    import sys

    proc = subprocess.Popen(
        [sys.executable, "-m", "whoop_mcp", "dashboard", "--reload", "--parent-pid", str(os.getpid())],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,  # stdout is the MCP protocol channel
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    atexit.register(proc.terminate)
    return True


def start_in_background() -> bool:
    """Start the dashboard in a daemon thread if the port is free (no reload).

    Returns False if something (e.g. a standalone dashboard) already owns the port.
    """
    if not port_free():
        return False
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host=config.HOST, port=config.PORT,
                                           log_level="warning", log_config=None))
    threading.Thread(target=server.run, name="whoop-dashboard", daemon=True).start()
    return True

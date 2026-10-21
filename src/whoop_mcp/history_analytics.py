"""Season-level analysis of the full history: training load, run intensity and sleep vs recovery.

Every function takes the `days` / `workouts` lists that `history.build_history` produces.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

TRAINING = ("swim", "bike", "run", "strength")


def _week_start(iso: str) -> date:
    d = date.fromisoformat(iso)
    return d - timedelta(days=d.weekday())


def weekly_load(days: list[dict[str, Any]], workouts: list[dict[str, Any]]) -> dict[str, Any]:
    """Hours per discipline and strain per ISO week (Monday start), plus days since each discipline."""
    if not days and not workouts:
        return {"weeks": [], "last_session": {}, "as_of": None}
    dates = [d["date"] for d in days] + [w["date"] for w in workouts]
    first, last = _week_start(min(dates)), date.fromisoformat(max(dates))

    weeks: dict[date, dict[str, Any]] = {}
    wk = first
    while wk <= last:
        weeks[wk] = {"week": str(wk), "hours": {k: 0.0 for k in TRAINING}, "sessions": 0, "strain": []}
        wk += timedelta(days=7)

    last_session: dict[str, str] = {}
    for w in workouts:
        disc = w["discipline"]
        if disc not in TRAINING:
            continue
        row = weeks[_week_start(w["date"])]
        row["hours"][disc] += (w["minutes"] or 0) / 60
        row["sessions"] += 1
        if w["date"] > last_session.get(disc, ""):
            last_session[disc] = w["date"]
    for d in days:
        if d.get("strain") is not None:
            weeks[_week_start(d["date"])]["strain"].append(d["strain"])

    out = []
    for row in weeks.values():
        s = row.pop("strain")
        row["hours"] = {k: round(v, 2) for k, v in row["hours"].items()}
        row["total_hours"] = round(sum(row["hours"].values()), 2)
        row["avg_strain"] = round(sum(s) / len(s), 1) if s else None
        out.append(row)

    since = {k: {"date": v, "days": (last - date.fromisoformat(v)).days} for k, v in last_session.items()}
    for k in TRAINING:
        since.setdefault(k, {"date": None, "days": None})
    return {"weeks": out, "last_session": since, "as_of": str(last)}

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


SLEEP_BUCKETS = [(0.0, 6.5), (6.5, 7.5), (7.5, 8.5), (8.5, 24.0)]
MIN_NIGHTS = 5  # a bucket needs this many nights before it can set the target


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return round(sxy / (sxx * syy) ** 0.5, 2) if sxx and syy else None


def sleep_recovery(days: list[dict[str, Any]]) -> dict[str, Any]:
    """How the night's sleep (hours asleep) relates to the morning's recovery.

    The suggested target is the shortest sleep bucket whose average recovery is within
    2 points of the best bucket, so it does not ask for more sleep than pays off.
    """
    points = [{"date": d["date"], "sleep_h": d["sleep_h"], "recovery": d["recovery"]}
              for d in days if d.get("sleep_h") is not None and d.get("recovery") is not None]
    buckets = []
    for lo, hi in SLEEP_BUCKETS:
        rs = [p["recovery"] for p in points if lo <= p["sleep_h"] < hi]
        buckets.append({"low": lo, "high": None if hi >= 24 else hi, "nights": len(rs),
                        "avg_recovery": round(sum(rs) / len(rs), 1) if rs else None})
    usable = [b for b in buckets if b["nights"] >= MIN_NIGHTS]
    target = None
    if usable:
        best = max(b["avg_recovery"] for b in usable)
        target = next(b["low"] for b in usable if b["avg_recovery"] >= best - 2)
    return {
        "points": points,
        "buckets": buckets,
        "correlation": _pearson([p["sleep_h"] for p in points], [p["recovery"] for p in points]),
        "target_h": target,
    }


# WHOOP zones are % of max HR: Z1 50-60, Z2 60-70, Z3 70-80, Z4 80-90, Z5 90-100. Zone 0 (below 50 %)
# is warm-up/standing time and is left out. "Easy" is Z1+Z2; an 80 % easy share is the usual
# polarised-training guideline for endurance athletes.
EASY_TARGET_PCT = 80


def _zone_summary(minutes: list[float], runs: int) -> dict[str, Any]:
    total = sum(minutes)
    pct = [round(100 * m / total, 1) if total else 0.0 for m in minutes]
    return {"runs": runs, "minutes": [round(m, 1) for m in minutes], "pct": pct,
            "easy_pct": round(pct[0] + pct[1], 1) if total else None}


def run_zones(workouts: list[dict[str, Any]], discipline: str = "run") -> dict[str, Any]:
    """Time in HR zones 1-5 for one discipline, per month and overall."""
    months: dict[str, list[float]] = defaultdict(lambda: [0.0] * 5)
    counts: dict[str, int] = defaultdict(int)
    for w in workouts:
        if w["discipline"] != discipline:
            continue
        z = (w.get("zones") or [0] * 6)[1:6]
        if not any(z):
            continue
        m = w["date"][:7]
        counts[m] += 1
        months[m] = [a + (b or 0) for a, b in zip(months[m], z)]
    overall = [sum(v[i] for v in months.values()) for i in range(5)]
    return {
        "discipline": discipline,
        "easy_target_pct": EASY_TARGET_PCT,
        "overall": _zone_summary(overall, sum(counts.values())),
        "months": [{"month": m, **_zone_summary(months[m], counts[m])} for m in sorted(months)],
    }

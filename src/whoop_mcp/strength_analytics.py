"""Strength progress from the log: estimated 1RM and PRs, volume, muscle balance and the recovery link.

Pure functions over `strength.list_sessions()` / `list_exercises()` output plus a date -> recovery map.
Warm-up sets are left out of every number.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

# Epley is reliable up to ~12 reps; higher-rep sets still count for volume but not for 1RM.
MAX_E1RM_REPS = 12
# Weekly working sets per muscle: under 4 rarely maintains strength, 6-12 suits a triathlete's
# full-body maintenance/build, above ~12 starts to cost run/bike quality.
SET_TARGETS = {"low": 4, "high": 12}
SECONDARY_SHARE = 0.5  # a set counts fully for the main muscle and half for the others


def e1rm(kg: float, reps: int) -> float | None:
    if kg <= 0 or reps <= 0 or reps > MAX_E1RM_REPS:
        return None
    return round(kg if reps == 1 else kg * (1 + reps / 30), 1)


def _load(s: dict[str, Any], ex: dict[str, Any], body_kg: float | None) -> float:
    return s["weight_kg"] + (body_kg or 0) if ex["bodyweight"] else s["weight_kg"]


def _week(iso: str) -> str:
    d = date.fromisoformat(iso)
    return str(d - timedelta(days=d.weekday()))


def exercise_progress(sessions: list[dict[str, Any]], exercises: list[dict[str, Any]],
                      body_kg: float | None = None) -> list[dict[str, Any]]:
    """Per exercise: one point per session (best e1RM, best set, volume) with PRs flagged."""
    by_id = {e["id"]: e for e in exercises}
    points: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sess in sorted(sessions, key=lambda s: (s["date"], s["id"])):
        per: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for s in sess["sets"]:
            if not s["warmup"]:
                per[s["exercise_id"]].append(s)
        for ex_id, sets in per.items():
            ex = by_id[ex_id]
            loads = [(_load(s, ex, body_kg), s["reps"], s) for s in sets]
            scored = [(e1rm(kg, r), kg, r) for kg, r, _ in loads]
            best = max((x for x in scored if x[0] is not None), default=None)
            top = max(loads, key=lambda x: (x[0], x[1]))
            points[ex_id].append({
                "date": sess["date"], "session_id": sess["id"], "sets": len(sets),
                "reps": sum(r for _, r, _ in loads),
                "volume_kg": round(sum(kg * r for kg, r, _ in loads), 1),
                "e1rm": best[0] if best else None,
                "top_set": {"kg": top[0], "reps": top[1]},
            })
    out = []
    for ex_id, pts in points.items():
        best_so_far = None
        for p in pts:
            p["pr"] = p["e1rm"] is not None and (best_so_far is None or p["e1rm"] > best_so_far)
            if p["pr"]:
                best_so_far = p["e1rm"]
        ex = by_id[ex_id]
        last = pts[-1]
        earlier = [p["e1rm"] for p in pts if p["e1rm"] is not None
                   and date.fromisoformat(p["date"]) <= date.fromisoformat(last["date"]) - timedelta(days=28)]
        out.append({
            "exercise_id": ex_id, "name": ex["name"], "pattern": ex["pattern"], "muscles": ex["muscles"],
            "sessions": len(pts), "last_date": last["date"], "pr_e1rm": best_so_far,
            "pr_date": next((p["date"] for p in reversed(pts) if p["pr"]), None),
            "change_4w_pct": round(100 * (last["e1rm"] / earlier[-1] - 1), 1) if earlier and last["e1rm"] else None,
            "points": pts,
        })
    return sorted(out, key=lambda e: (-e["sessions"], e["name"]))


def weekly_balance(sessions: list[dict[str, Any]], exercises: list[dict[str, Any]]) -> dict[str, Any]:
    """Working sets per muscle, push/pull and upper/lower/core for each week."""
    by_id = {e["id"]: e for e in exercises}
    weeks: dict[str, dict[str, Any]] = {}
    for sess in sessions:
        w = weeks.setdefault(_week(sess["date"]), {
            "week": _week(sess["date"]), "sessions": 0, "sets": 0, "volume_kg": 0.0,
            "muscles": defaultdict(float), "push": 0, "pull": 0, "region": defaultdict(int)})
        w["sessions"] += 1
        for s in sess["sets"]:
            if s["warmup"]:
                continue
            ex = by_id[s["exercise_id"]]
            w["sets"] += 1
            w["volume_kg"] += s["weight_kg"] * s["reps"]
            for i, m in enumerate(ex["muscles"]):
                w["muscles"][m] += 1 if i == 0 else SECONDARY_SHARE
            if ex["push_pull"] in ("push", "pull"):
                w[ex["push_pull"]] += 1
            w["region"][ex["region"]] += 1
    out = []
    for k in sorted(weeks):
        w = weeks[k]
        out.append({**w, "volume_kg": round(w["volume_kg"], 1), "muscles": dict(w["muscles"]), "region": dict(w["region"])})
    return {"targets": SET_TARGETS, "weeks": out}


def recovery_link(sessions: list[dict[str, Any]], progress: list[dict[str, Any]],
                  recovery: dict[str, float]) -> dict[str, Any]:
    """Session performance vs that morning's recovery, and the next morning's recovery after lifting.

    Performance is the session's average e1RM as a % of each exercise's best before that day,
    so it compares like with like across exercises.
    """
    best_before: dict[tuple[int, str], float] = {}
    for ex in progress:
        best = None
        for p in ex["points"]:
            if best is not None:
                best_before[(ex["exercise_id"], p["date"])] = best
            if p["e1rm"] is not None:
                best = max(best or 0, p["e1rm"])
    per_session = []
    for sess in sessions:
        ratios = [100 * p["e1rm"] / best_before[(ex["exercise_id"], p["date"])]
                  for ex in progress for p in ex["points"]
                  if p["session_id"] == sess["id"] and p["e1rm"] and (ex["exercise_id"], p["date"]) in best_before]
        nxt = str(date.fromisoformat(sess["date"]) + timedelta(days=1))
        per_session.append({
            "session_id": sess["id"], "date": sess["date"], "recovery": recovery.get(sess["date"]),
            "next_recovery": recovery.get(nxt),
            "performance_pct": round(sum(ratios) / len(ratios), 1) if ratios else None,
        })
    zones = {"green": (67, 101), "yellow": (34, 67), "red": (0, 34)}
    by_zone = {}
    for z, (lo, hi) in zones.items():
        xs = [s["performance_pct"] for s in per_session
              if s["performance_pct"] is not None and s["recovery"] is not None and lo <= s["recovery"] < hi]
        by_zone[z] = {"sessions": len(xs), "avg_performance_pct": round(sum(xs) / len(xs), 1) if xs else None}
    drops = [s["recovery"] - s["next_recovery"] for s in per_session
             if s["recovery"] is not None and s["next_recovery"] is not None]
    return {"sessions": per_session, "by_zone": by_zone,
            "avg_next_day_change": round(-sum(drops) / len(drops), 1) if drops else None}


def summary(sessions, exercises, recovery: dict[str, float], body_kg: float | None = None) -> dict[str, Any]:
    progress = exercise_progress(sessions, exercises, body_kg)
    return {
        "sessions": len(sessions),
        "progress": progress,
        "balance": weekly_balance(sessions, exercises),
        "recovery": recovery_link(sessions, progress, recovery),
    }

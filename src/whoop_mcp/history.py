"""Full-history payload for the dashboard, built from the latest export's CSV files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from . import history_analytics as ha
from .export import latest_export


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _num(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _r(v: float | None, d: int = 1) -> float | None:
    return None if v is None else round(v, d)


def build_history() -> dict[str, Any]:
    root = latest_export()
    if root is None:
        return {"available": False}

    sleeps = {s["id"]: s for s in _rows(root / "sleeps_summary.csv")}
    cycles = {c["id"]: c for c in _rows(root / "cycles.csv")}

    days: dict[str, dict[str, Any]] = {}

    def day(d: str) -> dict[str, Any]:
        return days.setdefault(d, {"date": d})

    for s in sleeps.values():
        if s.get("nap") == "True" or not s.get("date"):
            continue
        d = day(s["date"])
        d.update(
            sleep_h=_num(s.get("hours_asleep")), sleep_perf=_num(s.get("performance_pct")),
            efficiency=_num(s.get("efficiency_pct")), consistency=_num(s.get("consistency_pct")),
            need_h=_num(s.get("hours_needed")), resp=_num(s.get("respiratory_rate")),
            deep_h=_num(s.get("stages_h.deep_sws")), rem_h=_num(s.get("stages_h.rem")),
            light_h=_num(s.get("stages_h.light")), awake_h=_num(s.get("stages_h.awake")),
        )

    for r in _rows(root / "recoveries.csv"):
        s = sleeps.get(r.get("sleep_id", ""))
        if not s or not s.get("date"):
            continue
        d = day(s["date"])
        d.update(
            recovery=_num(r.get("score.recovery_score")), hrv=_r(_num(r.get("score.hrv_rmssd_milli"))),
            rhr=_num(r.get("score.resting_heart_rate")), spo2=_r(_num(r.get("score.spo2_percentage"))),
            skin_temp=_r(_num(r.get("score.skin_temp_celsius")), 2),
        )
        c = cycles.get(r.get("cycle_id", ""))
        if c:
            d.update(strain=_r(_num(c.get("score.strain"))), kj=_r(_num(c.get("score.kilojoule")), 0),
                     steps=_num(c.get("step_count")))

    # Workouts belong to the cycle day they started in; the cycle's recovery date is that day's label.
    workouts = []
    for w in _rows(root / "workouts_summary.csv"):
        workouts.append({
            "date": w["date"], "start": w["start"], "sport": w["sport"], "discipline": w["discipline"],
            "minutes": _num(w["duration_min"]), "strain": _num(w["strain"]), "avg_hr": _num(w["avg_hr"]),
            "max_hr": _num(w["max_hr"]), "kj": _num(w["kilojoules"]), "km": _num(w["distance_km"]),
            "zones": [_num(w.get(f"zone_minutes.z{i}")) or 0 for i in range(6)],
        })

    monthly = _rows(root / "monthly_summary.csv")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    series = [days[k] for k in sorted(days)]
    analytics = {"load": ha.weekly_load(series, workouts)}
    return {
        "available": True,
        "exported_at": manifest.get("exported_at"),
        "counts": manifest.get("counts"),
        "body": manifest.get("body"),
        "days": series,
        "workouts": workouts,
        "analytics": analytics,
        "monthly": [{k: (_num(v) if k != "month" else v) for k, v in m.items()} for m in monthly],
    }

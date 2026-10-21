"""Weekly Half Ironman (70.3) plan built around the athlete's own training habits and today's recovery.

The week is a fixed set of session slots (swim/bike/run/strength) placed on the days the athlete
usually does each sport, sized from the weekly-hours setting and the phase (weeks to race).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from . import config

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEFAULTS: dict[str, Any] = {
    "race_name": "Half Ironman (70.3)",
    "race_date": None,          # YYYY-MM-DD; without it the plan stays in base
    "weekly_hours": 8.0,        # endurance + strength
    "strength_days": None,      # e.g. [0, 3]; None = taken from history
    "long_ride_day": 5,         # Sat
    "long_run_day": 6,          # Sun
    "rest_day": 4,              # Fri
}

# Phase by weeks to race: (name, strength sessions, strength minutes, focus)
PHASES = [
    (16, "base", 2, 45, "Aerobic base: mostly Z2, technique in the water, full-body strength twice a week."),
    (7, "build", 2, 40, "Race-specific work: sweet-spot bike, tempo runs, a brick run off the long ride."),
    (3, "peak", 1, 30, "Longest race-pace sessions; strength drops to one short maintenance session."),
    (1, "taper", 1, 20, "Volume down 40-50%, keep some intensity, stay fresh."),
    (0, "race week", 0, 0, "Short openers, sleep, fuel. Race day."),
]
# Endurance slots per phase: (sport, kind, share of endurance minutes, intensity, description)
SLOTS: dict[str, list[tuple[str, str, float, str, str]]] = {
    "base": [
        ("swim", "technique", 0.06, "Z1-Z2", "Drills + 6x100 m easy, focus on catch and breathing"),
        ("swim", "endurance", 0.08, "Z2", "Continuous 1500-2000 m, steady"),
        ("bike", "endurance", 0.14, "Z2", "Steady Z2 ride, high cadence"),
        ("bike", "quality", 0.10, "Z3", "3x10 min tempo, 5 min easy between"),
        ("bike", "long", 0.24, "Z2", "Long ride, practise fuelling every 20 min"),
        ("run", "easy", 0.09, "Z2", "Easy run + 6x20 s strides"),
        ("run", "quality", 0.11, "Z2-Z3", "Hill or tempo run, conversational most of the time"),
        ("run", "long", 0.18, "Z2", "Long easy run"),
    ],
    "build": [
        ("swim", "technique", 0.05, "Z2", "Drills + 8x100 m at race pace"),
        ("swim", "endurance", 0.09, "Z2-Z3", "2000-2500 m with 3x400 m at race effort"),
        ("bike", "endurance", 0.12, "Z2", "Steady Z2 ride"),
        ("bike", "quality", 0.12, "Z3-Z4", "3x15 min sweet spot (88-93% FTP)"),
        ("bike", "long", 0.24, "Z2-Z3", "Long ride with 2x20 min at race power"),
        ("run", "brick", 0.05, "Z3", "Run straight off the long ride at race pace"),
        ("run", "quality", 0.13, "Z3-Z4", "Tempo: 3x2 km at half-marathon pace"),
        ("run", "long", 0.20, "Z2", "Long run, last 3 km at race pace"),
    ],
}
SLOTS["peak"] = SLOTS["build"]
SLOTS["taper"] = SLOTS["build"]
SLOTS["race week"] = [
    ("swim", "technique", 0.25, "Z2", "20 min easy with 4x50 m race pace"),
    ("bike", "quality", 0.4, "Z2-Z3", "40 min easy with 3x3 min at race power"),
    ("run", "easy", 0.35, "Z2", "20 min easy with 4 strides"),
]
TAPER_VOLUME = {"taper": 0.6, "race week": 0.35}
MIN_SESSION = {"swim": 20, "bike": 30, "run": 20}


# --------------------------------------------------------------------------- settings

def load_settings() -> dict[str, Any]:
    try:
        data = json.loads(config.PLAN_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    s = load_settings()
    for k, v in patch.items():
        if k not in DEFAULTS:
            raise ValueError(f"unknown setting {k!r}")
        s[k] = v
    if s["race_date"]:
        date.fromisoformat(s["race_date"])
    hours = float(s["weekly_hours"])
    if not 3 <= hours <= 25:
        raise ValueError("weekly_hours must be 3-25")
    s["weekly_hours"] = hours
    for k in ("long_ride_day", "long_run_day", "rest_day"):
        if s[k] not in range(7):
            raise ValueError(f"{k} must be 0 (Mon) to 6 (Sun)")
    if s["strength_days"] is not None:
        if not isinstance(s["strength_days"], list) or not all(d in range(7) for d in s["strength_days"]) or len(s["strength_days"]) > 3:
            raise ValueError("strength_days must be up to 3 weekdays, 0 (Mon) to 6 (Sun)")
        s["strength_days"] = sorted(set(s["strength_days"]))
    if len({s["long_ride_day"], s["long_run_day"], s["rest_day"]}) < 3:
        raise ValueError("long ride, long run and rest must be on different days")
    s["race_name"] = str(s["race_name"] or DEFAULTS["race_name"])[:80]
    config.PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config.PLAN_FILE.parent, prefix=".plan-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, config.PLAN_FILE)
    return s


# --------------------------------------------------------------------------- habits

def _local_start(w: dict[str, Any]) -> datetime | None:
    """Start time in the athlete's local time (WHOOP stores UTC plus the offset at the time)."""
    try:
        t = datetime.fromisoformat(w["start"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError):
        return None
    off = w.get("timezone_offset")
    if off and re.fullmatch(r"[+-]\d{2}:\d{2}", off):
        sign = 1 if off[0] == "+" else -1
        t = t + sign * timedelta(hours=int(off[1:3]), minutes=int(off[4:6]))
    return t


def habits(workouts: list[dict[str, Any]], weeks: int = 26) -> dict[str, Any]:
    """How often each sport happens on each weekday (sessions per week) over the recent weeks with
    training, and the usual start hour. `workouts` need date, discipline and start."""
    train = [w for w in workouts if w.get("discipline") in ("swim", "bike", "run", "strength") and w.get("date")]
    if not train:
        return {"weeks": 0, "by_day": [{} for _ in DAYS], "hours": {}}
    last = max(date.fromisoformat(w["date"]) for w in train)
    recent = [w for w in train if (last - date.fromisoformat(w["date"])).days < weeks * 7]
    week_ids = {date.fromisoformat(w["date"]) - timedelta(days=date.fromisoformat(w["date"]).weekday()) for w in recent}
    n = max(1, len(week_ids))
    by_day: list[Counter] = [Counter() for _ in DAYS]
    hours: dict[str, Counter] = defaultdict(Counter)
    for w in recent:
        d = date.fromisoformat(w["date"])
        by_day[d.weekday()][w["discipline"]] += 1
        t = _local_start(w)
        if t:
            hours[w["discipline"]][t.hour] += 1
    return {
        "weeks": n,
        "by_day": [{k: round(v / n, 2) for k, v in c.items()} for c in by_day],
        "hours": {k: c.most_common(1)[0][0] for k, c in hours.items()},
    }


def default_strength_days(h: dict[str, Any], count: int = 2) -> list[int]:
    """The most common strength weekdays, at least two days apart so legs recover between sessions."""
    ranked = sorted(range(7), key=lambda d: -h["by_day"][d].get("strength", 0))
    picked: list[int] = []
    for d in ranked:
        if len(picked) == count:
            break
        if all(min(abs(d - p), 7 - abs(d - p)) >= 2 for p in picked):
            picked.append(d)
    return sorted(picked) or [0, 3][:count]


# --------------------------------------------------------------------------- plan

def phase_for(race_date: str | None, today: date) -> dict[str, Any]:
    if not race_date:
        name, strength_n, strength_min, focus = PHASES[0][1:]
        return {"name": name, "weeks_to_race": None, "strength_sessions": strength_n, "strength_min": strength_min,
                "focus": focus + " Set a race date to move through build, peak and taper."}
    weeks = (date.fromisoformat(race_date) - today).days // 7
    for min_weeks, name, strength_n, strength_min, focus in PHASES:
        if weeks >= min_weeks:
            return {"name": name, "weeks_to_race": weeks, "strength_sessions": strength_n,
                    "strength_min": strength_min, "focus": focus}
    return {"name": "post-race", "weeks_to_race": weeks, "strength_sessions": 2, "strength_min": 40,
            "focus": "Race is done: a recovery week, then pick the next goal."}


def _place(slots, settings: dict[str, Any], strength_days: list[int], h: dict[str, Any]) -> dict[int, list[dict]]:
    """Long ride/run on their days, quality away from strength days, the rest on habitual days."""
    week: dict[int, list[dict]] = {d: [] for d in range(7)}
    rest = settings["rest_day"]
    open_days = [d for d in range(7) if d != rest]

    def load(d):
        return len(week[d])

    def best_day(sport: str, avoid: set[int]) -> int:
        cands = [d for d in open_days if d not in avoid] or open_days
        # not twice the same sport in a day, then fewest sessions, then the athlete's habit
        return min(cands, key=lambda d: (any(s["sport"] == sport for s in week[d]), load(d), -h["by_day"][d].get(sport, 0), d))

    for d in strength_days:
        week[d].append({"sport": "strength", "kind": "full body"})
    taken_quality: set[int] = set()
    # Fixed and hard sessions first, so the easy ones fill in around them.
    order = {"long": 0, "brick": 0, "quality": 1}
    for sport, kind, share, intensity, desc in sorted(slots, key=lambda x: order.get(x[1], 2)):
        s = {"sport": sport, "kind": kind, "share": share, "intensity": intensity, "description": desc}
        if kind == "long":
            day = settings["long_ride_day"] if sport == "bike" else settings["long_run_day"]
        elif kind == "brick":
            day = settings["long_ride_day"]
        elif kind == "quality":
            # hard endurance days stay off strength days and the day before a long session
            longs = {settings["long_ride_day"], settings["long_run_day"]}
            avoid = set(strength_days) | taken_quality | longs | {(d - 1) % 7 for d in longs}
            day = best_day(sport, avoid)
            taken_quality.add(day)
        else:
            day = best_day(sport, {settings["long_ride_day"], settings["long_run_day"]})
        week[day].append(s)
    return week


def build_week(settings: dict[str, Any], h: dict[str, Any], today: date) -> dict[str, Any]:
    phase = phase_for(settings["race_date"], today)
    slots_name = phase["name"] if phase["name"] in SLOTS else "base"
    slots = SLOTS[slots_name]
    strength_days = (settings["strength_days"] or default_strength_days(h, 2))[: phase["strength_sessions"]]
    total_min = settings["weekly_hours"] * 60 * TAPER_VOLUME.get(phase["name"], 1.0)
    endurance_min = max(0.0, total_min - len(strength_days) * phase["strength_min"])
    share_sum = sum(s[2] for s in slots)
    week = _place(slots, settings, strength_days, h)

    monday = today - timedelta(days=today.weekday())
    days = []
    for d in range(7):
        sessions = []
        for s in week[d]:
            if s["sport"] == "strength":
                sessions.append({"sport": "strength", "kind": "full body", "minutes": phase["strength_min"], "intensity": "RPE 7-8",
                                 "description": "Squat or lunge, hinge, push, pull, core: 3x5-8, stop 2 reps short of failure",
                                 "hour": h["hours"].get("strength")})
            else:
                minutes = max(MIN_SESSION[s["sport"]], round(endurance_min * s["share"] / share_sum / 5) * 5)
                sessions.append({"sport": s["sport"], "kind": s["kind"], "minutes": minutes, "intensity": s["intensity"],
                                 "description": s["description"], "hour": h["hours"].get(s["sport"])})
        days.append({"date": str(monday + timedelta(days=d)), "weekday": DAYS[d], "rest": d == settings["rest_day"], "sessions": sessions})
    planned = {k: sum(x["minutes"] for day in days for x in day["sessions"] if x["sport"] == k) for k in ("swim", "bike", "run", "strength")}
    return {"phase": phase, "strength_days": strength_days, "days": days, "planned_minutes": planned}


def adjust_for_recovery(session: dict[str, Any], recovery: float | None) -> dict[str, Any] | None:
    """What to do with a planned session given this morning's recovery (WHOOP zones)."""
    if recovery is None:
        return None
    if recovery >= 67:
        return {"zone": "green", "action": "as planned", "note": "Green: do it as written."}
    if recovery >= 34:
        if session["kind"] in ("quality", "brick"):
            return {"zone": "yellow", "action": "cap intensity", "note": "Yellow: keep the duration, hold it in Z2."}
        if session["sport"] == "strength":
            return {"zone": "yellow", "action": "lighter", "note": "Yellow: same lifts, one set fewer, RPE 6-7."}
        return {"zone": "yellow", "action": "as planned", "note": "Yellow: fine as written, stay in the stated zone."}
    if session["sport"] == "strength":
        return {"zone": "red", "action": "swap", "note": "Red: swap for 20 min mobility; lift on the next green or yellow day."}
    return {"zone": "red", "action": "swap", "note": f"Red: replace with {20 if session['sport'] != 'bike' else 30} min very easy, or rest."}


def mark_done(week: dict[str, Any], workouts: list[dict[str, Any]]) -> None:
    """Tick off planned sessions that a WHOOP workout of the same sport covered on that day."""
    by_day: dict[str, list[dict]] = defaultdict(list)
    for w in workouts:
        by_day[w["date"]].append(w)
    for day in week["days"]:
        pool = list(by_day.get(day["date"], []))
        for s in day["sessions"]:
            match = next((w for w in pool if w["discipline"] == s["sport"]), None)
            s["done"] = match is not None
            if match:
                s["done_minutes"] = match.get("duration_min")
                pool.remove(match)
        day["extra"] = [{"sport": w["discipline"], "minutes": w.get("duration_min")} for w in pool
                        if w["discipline"] in ("swim", "bike", "run", "strength")]

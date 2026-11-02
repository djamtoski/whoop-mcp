"""Season program: a periodized Half Ironman (70.3) plan from today to race day, built the Claude Coach way.

Where `plan.py` sizes one week from habits, this lays out every week to the race: phases (base 1,
base 2, build, peak, taper, race week), 3:1 load/recovery cycles, swim/bike/run sessions that
progress week by week, and the athlete's full-body A/B/C strength sessions with sets, reps and
target RPE. Loads in kg are filled in at view time from the strength log's estimated 1RMs.

The output follows Claude Coach's TrainingPlan JSON (meta, preferences, assessment, zones, phases,
weeks -> days -> workouts, raceStrategy) with one addition: strength workouts carry `exercises`.
Every workout's `durationMinutes` is the sum of the parts in `humanReadable`.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import date, timedelta
from typing import Any

from . import config

DEFAULTS: dict[str, Any] = {
    "race_name": "Half Ironman 70.3",
    "race_date": "2027-09-12",
    "start_date": "2026-11-09",
    "weekly_hours": 8.5,      # base target; build weeks go above it
    "bike": "gym",            # gym | road
    "run_lthr": None,         # bpm from the 30 min run test; None = estimated from max HR
    "bike_lthr": None,        # bpm from the 20 min bike test
    "css": None,              # "m:ss" per 100 m from the 400/200 m test
}
BIKES = ("gym", "road")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SWIM_MIN_PER_100 = 2.4        # time per 100 m including rest, until a CSS test says otherwise
OPEN_WATER_FROM = (6, 1)      # Lake Ohrid is swimmable from about June

# --------------------------------------------------------------------------- settings


def load_settings() -> dict[str, Any]:
    try:
        data = json.loads(config.PROGRAM_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _parse_css(css: str) -> int | None:
    try:
        m, s = str(css).split(":")
        sec = int(m) * 60 + int(s)
    except (TypeError, ValueError):
        return None
    return sec if 60 <= sec <= 240 else None


def _normalize_settings(patch: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    s = load_settings()
    for k, v in patch.items():
        if k not in DEFAULTS:
            return None, f"unknown setting {k!r}"
        s[k] = v
    try:
        start, race = date.fromisoformat(s["start_date"]), date.fromisoformat(s["race_date"])
    except (TypeError, ValueError):
        return None, "start_date and race_date must be YYYY-MM-DD"
    weeks = (_monday(race) - _monday(start)).days // 7 + 1
    if not 8 <= weeks <= 60:
        return None, "the race must be 8 to 60 weeks after the start date"
    s["start_date"] = str(_monday(start))
    try:
        s["weekly_hours"] = float(s["weekly_hours"])
    except (TypeError, ValueError):
        return None, "weekly_hours must be a number"
    if not 4 <= s["weekly_hours"] <= 15:
        return None, "weekly_hours must be 4-15"
    if s["bike"] not in BIKES:
        return None, "bike must be gym or road"
    for k, lo, hi in (("run_lthr", 120, 200), ("bike_lthr", 115, 200)):
        if s[k] is not None:
            try:
                s[k] = int(s[k])
            except (TypeError, ValueError):
                return None, f"{k} must be a whole number of bpm"
            if not lo <= s[k] <= hi:
                return None, f"{k} must be {lo}-{hi} bpm"
    if s["css"] not in (None, "") and _parse_css(s["css"]) is None:
        return None, "css must be m:ss per 100 m, e.g. 1:55"
    s["css"] = s["css"] or None
    s["race_name"] = str(s["race_name"] or DEFAULTS["race_name"])[:80]
    return s, None


def check_settings(patch: dict[str, Any]) -> str | None:
    """Why save_settings would refuse `patch`, or None (a message, not an exception)."""
    return _normalize_settings(patch)[1]


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    s, problem = _normalize_settings(patch)
    if problem:
        raise ValueError(problem)
    config.PROGRAM_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config.PROGRAM_FILE.parent, prefix=".program-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, config.PROGRAM_FILE)
    return s


# --------------------------------------------------------------------------- load maths


def pct_1rm(reps: int, rpe: float) -> float:
    """Share of 1RM for `reps` at `rpe`: Epley with the reps left in reserve added (RPE 8 = 2 in reserve).

    5 @ RPE 8 -> 81%, 8 @ RPE 7 -> 73%, 1 @ RPE 10 -> 100%.
    """
    if reps == 1 and rpe >= 10:
        return 1.0
    return 1 / (1 + (reps + max(0.0, 10 - rpe)) / 30)


def e1rm(kg: float, reps: int, rpe: float | None = None) -> float | None:
    """Estimated 1RM from one set; with an RPE the reps in reserve count as if done."""
    if kg <= 0 or reps <= 0 or reps > 12:
        return None
    return round(kg / pct_1rm(reps, rpe if rpe is not None else 10), 1)


def round_load(kg: float, step: float) -> float:
    return round(round(kg / step) * step, 1)


# --------------------------------------------------------------------------- zones


def zones(settings: dict[str, Any], max_hr: int | None) -> dict[str, Any]:
    """Friel LTHR zones for run and bike, CSS zones for swim. Estimated until the week-1 tests."""
    est_run = round((max_hr or 185) * 0.9)
    run_lthr = settings["run_lthr"] or est_run
    bike_lthr = settings["bike_lthr"] or run_lthr - 6
    bands = [(1, "Recovery", 0, 81), (2, "Aerobic", 81, 89), (3, "Tempo", 90, 93),
             (4, "Sub-threshold", 94, 99), (5, "Threshold", 100, 102), (6, "VO2max", 103, 106)]

    def hr(lthr: int) -> list[dict[str, Any]]:
        return [{"zone": z, "name": n, "percentLow": lo, "percentHigh": hi,
                 "hrLow": round(lthr * lo / 100), "hrHigh": round(lthr * hi / 100)} for z, n, lo, hi in bands]

    css = _parse_css(settings["css"]) if settings["css"] else None
    swim = None
    if css:
        swim = [{"zone": z, "name": n, "paceOffset": off, "pace": f"{(css + off) // 60}:{(css + off) % 60:02d}/100m"}
                for z, n, off in ((1, "Recovery", 18), (2, "Aerobic", 10), (3, "Tempo", 5), (4, "Threshold", 0), (5, "VO2max", -4))]
    return {
        "run": {"hr": {"lthr": run_lthr, "estimated": settings["run_lthr"] is None, "zones": hr(run_lthr)}},
        "bike": {"hr": {"lthr": bike_lthr, "estimated": settings["bike_lthr"] is None, "zones": hr(bike_lthr)}},
        "swim": {"css": settings["css"], "cssSeconds": css, "estimated": css is None, "zones": swim},
    }


# --------------------------------------------------------------------------- phases

PHASE_INFO = {
    "base1": ("Base 1", "Aerobic engine and movement quality: easy swim/bike/run, technique in the pool, "
              "full-body A/B/C strength in the 6-8 rep range. Tests in week 1 set your zones and loads.",
              ["Long run", "Pool technique", "Full Body A"], ["Aerobic base", "Swim stroke efficiency", "Strength base"]),
    "base2": ("Base 2", "More bike, first tempo and sweet-spot work, a long ride on Sundays. Strength moves to "
              "heavier 4-6 rep sets.",
              ["Sweet-spot ride", "Tempo run", "Long ride"], ["Muscular endurance", "Raise threshold", "Max strength"]),
    "build": ("Build", "Race-specific: threshold intervals, long ride with race-power blocks, brick runs, open water. "
              "Strength drops to two sessions to protect the key endurance days.",
              ["Long ride + brick", "Threshold run", "Open-water swim"], ["Race-pace durability", "Brick tolerance", "Strength maintenance"]),
    "peak": ("Peak", "Longest race-pace sessions and a full race rehearsal. Strength is short, sharp and light.",
             ["Race simulation", "Race-pace long run"], ["Race specificity", "Fuelling rehearsal"]),
    "taper": ("Taper", "Volume down 30-50%, intensity kept in short doses. Arrive fresh.",
              ["Short race-pace openers"], ["Freshness"]),
    "race": ("Race week", "Openers, sleep, carbohydrate. Race on Sunday.", ["Race"], ["Execute"]),
}
# Week-load factor relative to the weekly-hours setting: (first, last) over the phase's load weeks.
RAMP = {"base1": (0.85, 1.0), "base2": (1.0, 1.1), "build": (1.1, 1.3), "peak": (1.25, 1.25)}
RECOVERY_FACTOR = 0.65


def phase_layout(n_weeks: int) -> list[dict[str, Any]]:
    """Phase blocks from the race backwards: race week 1, taper 2, peak 4, build up to 12, base the rest."""
    race, taper = 1, 2
    peak = 4 if n_weeks >= 20 else 2
    build = min(12, max(4, (n_weeks - race - taper - peak) // 2))
    base = n_weeks - race - taper - peak - build
    base1 = math.ceil(base / 2) if base >= 8 else base
    base2 = base - base1
    out, w = [], 1
    for key, length in (("base1", base1), ("base2", base2), ("build", build), ("peak", peak), ("taper", taper), ("race", race)):
        if length <= 0:
            continue
        name, focus, key_workouts, goals = PHASE_INFO[key]
        out.append({"key": key, "name": name, "startWeek": w, "endWeek": w + length - 1, "focus": focus,
                    "keyWorkouts": key_workouts, "physiologicalGoals": goals})
        w += length
    return out


# --------------------------------------------------------------------------- workouts

def _r5(x: float) -> int:
    return max(5, int(round(x / 5) * 5))


def _r100(x: float) -> int:
    return max(100, int(round(x / 100) * 100))


def _pick(options: list[str], i: int) -> str:
    return options[min(i, len(options) - 1)]


def _wo(wid: str, sport: str, kind: str, name: str, parts: list[tuple[int, str]], zone: str, slot: str,
        why: str, **extra: Any) -> dict[str, Any]:
    """A workout whose duration is the sum of its parts (minutes, description)."""
    return {"id": wid, "sport": sport, "type": kind, "name": name, "description": why,
            "durationMinutes": sum(m for m, _ in parts), "primaryZone": zone, "slot": slot,
            "humanReadable": "\n".join(f"{m} min · {t}" for m, t in parts), "completed": False,
            "parts": [list(x) for x in parts], **extra}


def _fit_to_hours(days: list[dict[str, Any]], target_h: float) -> None:
    """Trim easy and long bike/run sessions when a week runs more than 5% over its hours target.

    Only the longest part of each of those workouts shrinks, so warm-ups, cool-downs and intervals
    keep their shape; durationMinutes and humanReadable change together.
    """
    wos = [w for d in days for w in d["workouts"] if w["sport"] not in ("rest", "race")]
    total = sum(w["durationMinutes"] for w in wos) / 60
    if total <= target_h * 1.05:
        return
    flex = [w for w in wos if w["sport"] in ("bike", "run") and w["type"] in ("long", "endurance", "easy") and w.get("parts")]
    flex_h = sum(w["durationMinutes"] for w in flex) / 60
    if not flex_h:
        return
    ratio = max(0.6, 1 - (total - target_h) / flex_h)
    for w in flex:
        idx = max(range(len(w["parts"])), key=lambda i: w["parts"][i][0])
        w["parts"][idx][0] = _r5(w["parts"][idx][0] * ratio)
        w["durationMinutes"] = sum(m for m, _ in w["parts"])
        w["humanReadable"] = "\n".join(f"{m} min · {t}" for m, t in w["parts"])


def _swim(wid: str, kind: str, name: str, sets: list[tuple[int, str]], zone: str, slot: str, why: str,
          rest_min: int = 0) -> dict[str, Any]:
    """A swim given as (metres, description) sets; minutes estimated at SWIM_MIN_PER_100 including rest.
    `rest_min` is a timed pause (e.g. between test efforts) added as its own part."""
    parts = [(max(1, round(m / 100 * SWIM_MIN_PER_100)), f"{m} m {t}") for m, t in sets]
    if rest_min:
        parts.insert(2, (rest_min, "easy swimming or rest before the next effort"))
    return _wo(wid, "swim", kind, name, parts, zone, slot, why, distanceMeters=sum(m for m, _ in sets))


def _bike_where(settings: dict[str, Any], d: date, long: bool = False) -> str:
    if settings["bike"] == "road" and (long or d.month in (4, 5, 6, 7, 8, 9)):
        return "road bike, outdoors"
    return "gym bike (indoor)"


RUN_TEMPO = ["3×6 min Z3, 2 min jog", "3×8 min Z3, 2 min jog", "2×12 min Z3, 3 min jog", "20 min Z3 continuous",
             "3×10 min Z3, 2 min jog", "2×15 min Z3, 3 min jog", "25 min Z3 continuous", "30 min Z3 continuous"]
RUN_THRESHOLD = ["5×5 min Z4, 2 min jog", "4×8 min Z4, 2 min jog", "3×10 min Z4, 3 min jog", "2×15 min Z4, 4 min jog",
                 "3×12 min Z4, 3 min jog", "2×20 min race pace (Z3), 4 min jog", "4×10 min Z4, 2 min jog",
                 "3×15 min race pace (Z3), 3 min jog", "40 min race pace (Z3)"]
BIKE_SWEETSPOT = ["3×8 min Z3-Z4, 4 min easy", "3×10 min Z3-Z4, 4 min easy", "3×12 min Z3-Z4, 4 min easy",
                  "2×15 min Z3-Z4, 5 min easy", "2×20 min Z3-Z4, 5 min easy", "3×15 min Z3-Z4, 5 min easy"]
BIKE_THRESHOLD = ["4×8 min Z4, 4 min easy", "3×12 min Z4, 5 min easy", "2×20 min Z4, 5 min easy",
                  "3×15 min Z4, 5 min easy", "2×25 min Z3-Z4, 5 min easy", "3×20 min race power (Z3), 5 min easy"]
SWIM_AEROBIC = ["6×100 m Z2, 20 s rest", "8×100 m Z2, 20 s rest", "4×200 m Z2, 30 s rest", "6×100 m CSS, 15 s rest",
                "8×100 m CSS, 15 s rest", "3×300 m Z2, 30 s rest", "10×100 m CSS, 15 s rest", "4×300 m Z2, 30 s rest"]
SWIM_CSS = ["10×100 m CSS, 15 s rest", "5×200 m CSS, 20 s rest", "4×300 m CSS+3 s, 30 s rest", "3×400 m Z3, 40 s rest",
            "12×100 m CSS, 15 s rest", "2×600 m Z3, 60 s rest"]


def _endurance(phase: str, i: int, p: float, f: float, rec: bool, week1: bool, d: list[date],
               settings: dict[str, Any], wn: int) -> dict[int, list[dict[str, Any]]]:
    """Swim/bike/run sessions for one week, keyed by weekday. `i` counts load weeks in the phase, `p` is
    progress through it (0-1), `f` the load factor."""
    w = f"w{wn}"
    s: dict[int, list[dict[str, Any]]] = {k: [] for k in range(7)}
    k = f  # load factor, recovery cut included
    open_water = lambda day: (day.month, day.day) >= OPEN_WATER_FROM and day.month <= 9  # noqa: E731

    if phase == "base1":
        if week1:
            s[0].append(_swim(f"{w}-mon-swim", "test", "CSS test", [(400, "easy with drills"), (400, "time trial, all out: note the time"),
                              (200, "time trial, all out: note the time"), (200, "easy")], "Test", "AM",
                              "CSS = 200 ÷ (400 m time − 200 m time). Enter it in Program settings; swim zones follow.", rest_min=10))
            s[1].append(_wo(f"{w}-tue-bike", "bike", "test", "20 min bike HR test",
                            [(20, "easy with 3×1 min high-cadence spin-ups"), (20, "hardest steady effort you can hold, note average HR"),
                             (10, "easy")], "Test", "PM", "Average HR of the 20 min = bike LTHR. Enter it in Program settings."))
            s[2].append(_wo(f"{w}-wed-run", "run", "test", "30 min run test",
                            [(15, "easy Z1-Z2"), (30, "hardest steady pace you can hold, note average HR of the last 20 min"),
                             (10, "easy")], "Test", "AM", "Average HR of the last 20 min = run LTHR. Enter it in Program settings."))
        else:
            s[0].append(_swim(f"{w}-mon-swim", "technique", "Technique + aerobic",
                              [(300, "easy"), (400, "drills: catch-up, fingertip drag, single arm (8×50)"),
                               (_r100((700 + 500 * p) * k), _pick(SWIM_AEROBIC, i)), (200, "easy")], "Z2", "AM",
                              "Stroke efficiency is the cheapest speed in triathlon."))
            s[1].append(_wo(f"{w}-tue-bike", "bike", "endurance", "Aerobic ride",
                            [(10, "easy spin"), (_r5((35 + 20 * p) * k), "Z2 steady, 5×1 min high cadence (100+ rpm) in the middle"),
                             (5, "easy")], "Z2", "PM", f"Builds the bike engine you have not trained yet. {_bike_where(settings, d[1]).capitalize()}."))
            s[2].append(_wo(f"{w}-wed-run", "run", "easy", "Easy run + strides",
                            [(_r5((30 + 15 * p) * k), "Z2, conversational"), (5, "6×20 s strides, walk back")], "Z2", "AM",
                            "Easy running builds durability without stealing from the evening lift."))
        s[3].append(_swim(f"{w}-thu-swim", "endurance", "Aerobic swim",
                          [(300, "easy"), (200, "4×50 m build"), (_r100((800 + 600 * p) * k), _pick(SWIM_AEROBIC, i + 2)), (200, "easy")],
                          "Z2", "AM", "Second weekly swim: volume and pacing."))
        s[3].append(_wo(f"{w}-thu-bike", "bike", "endurance", "Cadence ride",
                        [(10, "easy"), (_r5((25 + 15 * p) * k), "Z2" + (", with 3×5 min Z3" if p > 0.5 and not rec else "")), (5, "easy")],
                        "Z2", "PM", "Short ride, high cadence; legs stay fresh for Friday."))
        s[5].append(_wo(f"{w}-sat-run", "run", "long", "Long run",
                        [(max(40, _r5((45 + 30 * p) * k)), "Z2, flat route, walk breaks are fine")], "Z2", "AM",
                        "The most important run of the week. Glute activation before you head out."))
    elif phase == "base2":
        s[1].append(_swim(f"{w}-tue-swim", "quality", "CSS swim",
                          [(400, "easy + drills"), (200, "4×50 m build"), (_r100(1200 * k), _pick(SWIM_CSS, i)), (200, "easy")],
                          "Z4", "AM", "Threshold swimming: the set that makes 1900 m feel controlled."))
        s[1].append(_wo(f"{w}-tue-bike", "bike", "endurance", "Aerobic ride",
                        [(5, "easy"), (_r5((30 + 10 * p) * k), "Z2 steady, cadence 85-95"), (5, "easy")], "Z2", "PM",
                        _bike_where(settings, d[1]).capitalize() + "."))
        main = "easy Z2 only" if rec else _pick(RUN_TEMPO, i)
        s[2].append(_wo(f"{w}-wed-run", "run", "easy" if rec else "quality", "Easy run" if rec else "Tempo run",
                        [(15, "easy + 4 strides"), (_r5(25 * k) if rec else _r5(sum(_minutes(main)) or 20), main), (10, "easy")],
                        "Z2" if rec else "Z3", "AM", "Tempo raises the pace you can hold for 21 km."))
        bmain = "Z2 steady" if rec else _pick(BIKE_SWEETSPOT, i)
        s[3].append(_wo(f"{w}-thu-bike", "bike", "endurance" if rec else "quality", "Easy ride" if rec else "Sweet-spot ride",
                        [(15, "easy"), (_r5(30 * k) if rec else _r5(sum(_minutes(bmain))), bmain), (10, "easy")],
                        "Z2" if rec else "Z3-Z4", "AM", "Sweet spot: the best return per minute for a time-limited triathlete."))
        s[4].append(_swim(f"{w}-fri-swim", "endurance", "Aerobic swim",
                          [(300, "easy"), (_r100((900 + 1000 * p) * k), "continuous Z2, bilateral breathing"), (200, "easy")],
                          "Z2", "AM", "Builds to 1900 m continuous: race distance without stopping."))
        s[5].append(_wo(f"{w}-sat-run", "run", "long", "Long run", [(_r5((60 + 20 * p) * k), "Z2")], "Z2", "AM",
                        "Long run. Fuel with 30-40 g carbs per hour from 75 min."))
        s[6].append(_wo(f"{w}-sun-bike", "bike", "long", "Long ride",
                        [(_r5((60 + 30 * p) * k), "Z2, practise eating every 20 min")], "Z2", "AM",
                        _bike_where(settings, d[6], long=True).capitalize() + "."))
    elif phase in ("build", "peak"):
        peak = phase == "peak"
        k = f / 1.2  # build and peak factors sit around 1.2; sessions are written for that
        s[0].append(_swim(f"{w}-mon-swim", "endurance", "Aerobic swim",
                          [(400, "easy + drills"), (_r100((1500 if peak else 1100 + 700 * p) * k),
                                                    "continuous Z2" if p < 0.6 and not peak else "1900 m continuous at race effort"),
                           (200, "easy")], "Z2", "AM", "Swim volume at race distance."))
        tmain = "easy Z2" if rec else _pick(RUN_THRESHOLD, i + (5 if peak else 0))
        s[1].append(_wo(f"{w}-tue-run", "run", "easy" if rec else "quality", "Easy run" if rec else "Threshold run",
                        [(15, "easy + 4 strides"), (_r5(30 * k) if rec else _r5(sum(_minutes(tmain))), tmain), (10, "easy")],
                        "Z2" if rec else "Z4", "AM", "Threshold work lifts the ceiling your race pace sits under."))
        bmain = "Z2 steady" if rec else _pick(BIKE_THRESHOLD, i + (3 if peak else 0))
        s[2].append(_wo(f"{w}-wed-bike", "bike", "endurance" if rec else "quality", "Easy ride" if rec else "Threshold ride",
                        [(15, "easy"), (_r5(40 * k) if rec else _r5(sum(_minutes(bmain))), bmain), (10, "easy")],
                        "Z2" if rec else "Z4", "AM", _bike_where(settings, d[2]).capitalize() + "."))
        ow = open_water(d[3])
        s[3].append(_swim(f"{w}-thu-swim", "quality", "Open water" if ow else "CSS swim",
                          [(400, "easy + sighting every 6 strokes" if ow else "easy + drills"),
                           (_r100(1500 * k), "3×500 m race effort, practise sighting and drafting" if ow else _pick(SWIM_CSS, i + 2)),
                           (200, "easy")], "Z3-Z4", "AM", "Lake Ohrid: never swim alone; wetsuit if under 22 °C." if ow else "Pool CSS set."))
        s[3].append(_wo(f"{w}-thu-run", "run", "easy", "Easy run", [(_r5((35 + 10 * p) * k), "Z2")], "Z2", "PM", "Recovery-pace run."))
        long_ride = _r5((105 + 45 * p) * k) if not peak else _r5([150, 170, 140, 110][min(i, 3)] * k)
        race_blocks = "" if rec else (", with 2×20 min race power (Z3)" if p < 0.5 and not peak else ", with 3×20 min race power (Z3)")
        s[5].append(_wo(f"{w}-sat-bike", "bike", "long", "Long ride", [(long_ride, "Z2" + race_blocks + "; eat 60-80 g carbs per hour")],
                        "Z2-Z3", "AM", _bike_where(settings, d[5], long=True).capitalize() + "."))
        s[5].append(_wo(f"{w}-sat-brick", "run", "brick", "Brick run",
                        [(_r5((15 + 15 * p) * k) if not peak else _r5(30 * k), "straight off the bike: first 5 min race pace, then Z2")],
                        "Z3", "AM", "Teaches the legs to run off the bike."))
        long_run = _r5((75 + 25 * p) * k) if not peak else _r5([95, 105, 90, 80][min(i, 3)] * k)
        s[6].append(_wo(f"{w}-sun-run", "run", "long", "Long run",
                        [(long_run, "Z2" + ("" if rec or p < 0.4 else ", last 20 min at race pace (Z3)"))], "Z2", "AM",
                        "Durability for the last 10 km of the race."))
    elif phase == "taper":
        short = i == 1
        s[0].append(_swim(f"{w}-mon-swim", "endurance", "Easy swim", [(300, "easy"), (900 if short else 1300, "Z2 with 4×50 m race pace"), (200, "easy")],
                          "Z2", "AM", "Keep the feel for the water."))
        s[1].append(_wo(f"{w}-tue-run", "run", "quality", "Race-pace openers",
                        [(15, "easy"), (15 if short else 24, "3×5 min race pace, 2 min jog" if short else "3×8 min race pace, 2 min jog"), (10, "easy")],
                        "Z3", "AM", "Short intensity keeps you sharp while volume drops."))
        s[2].append(_wo(f"{w}-wed-bike", "bike", "quality", "Race-power openers",
                        [(15, "easy"), (24 if short else 36, "3×8 min race power" if short else "3×12 min race power"), (10, "easy")],
                        "Z3", "AM", _bike_where(settings, d[2]).capitalize() + "."))
        s[3].append(_swim(f"{w}-thu-swim", "quality", "Short race-pace swim", [(300, "easy"), (800 if short else 1200, "8×100 m race pace" if short else "3×400 m race pace"), (200, "easy")],
                          "Z3", "AM", "Open water if you can."))
        s[5].append(_wo(f"{w}-sat-bike", "bike", "long", "Shorter long ride", [(60 if short else 90, "Z2 with 2×10 min race power")], "Z2", "AM", "Last longer ride."))
        s[5].append(_wo(f"{w}-sat-brick", "run", "brick", "Brick run", [(10 if short else 15, "race pace off the bike")], "Z3", "AM", "Rehearse T2."))
        s[6].append(_wo(f"{w}-sun-run", "run", "long", "Easy long run", [(45 if short else 60, "Z2")], "Z2", "AM", "Volume down, legs fresh."))
    else:  # race week
        s[1].append(_swim(f"{w}-tue-swim", "technique", "Swim openers", [(300, "easy"), (400, "4×100 m race pace, 30 s rest"), (200, "easy")], "Z2-Z3", "AM", "Stay loose."))
        s[2].append(_wo(f"{w}-wed-bike", "bike", "quality", "Bike openers", [(15, "easy"), (15, "3×3 min race power, 2 min easy"), (10, "easy")], "Z2-Z3", "AM", "Check the bike works."))
        s[3].append(_wo(f"{w}-thu-run", "run", "easy", "Run openers", [(15, "easy"), (5, "4×20 s strides")], "Z2", "AM", "Last run before the race."))
        s[5].append(_wo(f"{w}-sat-shake", "bike", "easy", "Shake-out", [(20, "easy spin, 3×30 s race effort"), (10, "easy jog")], "Z1-Z2", "AM",
                        "Rack the bike, eat carbs, sleep."))
        s[6].append(_wo(f"{w}-sun-race", "race", "race", "RACE: Half Ironman 70.3",
                        [(45, "swim 1900 m"), (180, "bike 90 km"), (125, "run 21.1 km")], "Race", "AM",
                        "Pace the swim, ride under the line, run the last 10 km. Times are placeholders until your tests."))
    return s


def _minutes(text: str) -> list[int]:
    """Work minutes in an interval string like '3×10 min Z4, 3 min jog' (work plus recoveries between)."""
    import re

    m = re.match(r"(\d+)×(\d+) min", text)
    if m:
        r = re.search(r",\s*(\d+) min", text)
        n, work, rest = int(m[1]), int(m[2]), int(r[1]) if r else 0
        return [n * work + (n - 1) * rest]
    m = re.match(r"(\d+) min", text)
    return [int(m[1])] if m else []


# --------------------------------------------------------------------------- strength

# Main lifts get %1RM loads; reps_n is the rep count used for the load maths.
SHOULDER_PREP = {"name": "Left shoulder protocol", "kind": "prep", "sets": 1, "reps": "8 min",
                 "notes": "Thoracic extension on roller, sleeper stretch (left), wall push-plus (left), band external rotation (left), face pulls. Never skip before pressing."}
HIP_PREP = {"name": "Glute med activation + dead bug", "kind": "prep", "sets": 2, "reps": "15 + 8/side",
            "notes": "Hip abduction, lateral band walks, dead bug. Right hip: knee-out cue."}


def _scheme(phase: str, i: int, rec: bool, week1: bool) -> tuple[int, int, float, str]:
    """(sets, reps, rpe, label) for the main lifts this week."""
    if week1:
        return 3, 5, 8, "Calibration: work up to a top set of 5 at RPE 8, then 2 back-off sets of 5 at about −10%. Log every set with its RPE."
    if rec:
        return (2 if phase in ("build", "peak", "taper") else 3), 5, 6, "Deload: same lifts, lighter and fewer sets."
    table = {
        "base1": [(4, 8, 7), (4, 7, 7.5), (4, 6, 8)],
        "base2": [(4, 6, 7.5), (4, 5, 8), (5, 4, 8.5)],
        "build": [(3, 5, 7.5), (3, 4, 8), (3, 3, 8)],
        "peak": [(3, 3, 7.5), (3, 3, 7.5), (2, 3, 7), (2, 3, 7)],
        "taper": [(2, 3, 7), (2, 3, 6)],
    }[phase]
    sets, reps, rpe = table[i % len(table)] if phase not in ("peak", "taper") else table[min(i, len(table) - 1)]
    label = {"base1": "Hypertrophy-strength", "base2": "Strength", "build": "Strength maintenance",
             "peak": "Sharp and light", "taper": "Maintenance"}[phase]
    return sets, reps, rpe, label


def _main(name: str, sets: int, reps: int, rpe: float, rest: str, notes: str, per: str = "bar") -> dict[str, Any]:
    return {"name": name, "kind": "main", "sets": sets, "reps": str(reps), "reps_n": reps, "rpe": rpe, "rest": rest,
            "notes": notes, "per": per}


def _acc(name: str, sets: int, reps: str, rpe: float | None, rest: str, notes: str, reps_n: int | None = None,
         per: str = "bar", kind: str = "accessory") -> dict[str, Any]:
    return {"name": name, "kind": kind, "sets": sets, "reps": reps, "reps_n": reps_n, "rpe": rpe, "rest": rest,
            "notes": notes, "per": per}


def strength_session(letter: str, phase: str, i: int, rec: bool, week1: bool, wn: int, absolute_week: int) -> dict[str, Any]:
    """Full Body A (squat + press), B (hinge + overhead) or C (light legs before the long run, upper volume)."""
    sets, reps, rpe, label = _scheme(phase, i, rec, week1)
    acc_rpe = 6.5 if rec else (7.5 if phase in ("build", "peak", "taper") else 8)
    acc_sets = 2 if rec or phase in ("build", "peak", "taper") else 3
    # Weeks 1-4 dumbbell pressing for the left shoulder; barbell bench from week 5 if pain-free.
    press = "Incline Dumbbell Press" if absolute_week <= 4 else "Bench Press"
    press_note = ("Dumbbells let the left shoulder find its path. 3 s down, elbows ~45°. Load is per hand."
                  if press.startswith("Incline") else "Elbows ~45°, shoulder blades pinned. Back to dumbbells if the left shoulder twinges.")
    if letter == "A":
        ex = [HIP_PREP, _main("Back Squat", sets, reps, rpe, "2-4 min", "Full depth, knees out. First lift, freshest legs."),
              SHOULDER_PREP, _main(press, sets, reps + (2 if press.startswith("Incline") else 0), rpe, "2-3 min", press_note,
                                   per="hand" if press.startswith("Incline") else "bar"),
              _main("Pull-up", sets, max(reps, 5), min(rpe + 0.5, 9), "2-3 min", "Dead hang, no kipping. Load is added weight.", per="added"),
              _acc("Single-Leg Romanian Deadlift", acc_sets, "8/leg", acc_rpe, "90 s", "Right side: screw the foot into the floor.", 8, per="hand"),
              _acc("Nordic Hamstring Curl", 2, "4-6", acc_rpe, "2 min", "Slow lowering. Halves hamstring-strain risk."),
              _acc("Calf Raise", 3, "10/leg", None, "45 s", "Single leg, straight knee, 3 s lowering (gastrocnemius)."),
              _acc("Hanging Leg Raise", acc_sets, "10", acc_rpe, "60 s", "No swing.", kind="core")]
    elif letter == "B":
        ex = [{**HIP_PREP, "name": "Glute bridges + clamshells + dead bug"},
              _main("Romanian Deadlift", sets, reps + 1, rpe, "2-3 min", "Hips back, neutral spine, bar close."),
              {**SHOULDER_PREP, "reps": "5 min", "notes": "Band pull-aparts, wall slides, light lateral raises, face pulls."},
              _main("Overhead Press", sets, reps, rpe, "2-3 min", "Standing, brace before unracking. Stop if the left shoulder pinches."),
              _main("Chin-up", sets, max(reps, 5), min(rpe + 0.5, 9), "2-3 min", "Supinated grip, chest to bar. Load is added weight.", per="added"),
              _acc("Bulgarian Split Squat", acc_sets, "8/leg", acc_rpe, "2 min", "Front-heel drive. Load is per hand.", 8, per="hand"),
              _acc("Single-Arm Dumbbell Row", acc_sets, "10/side", acc_rpe, "90 s", "Anti-rotation: hips square.", 10, per="hand"),
              _acc("Copenhagen Plank", 2, "20-30 s/side", None, "45 s", "Adductors: protects groin and knees."),
              _acc("Calf Raise", 3, "10/leg", None, "45 s", "Single leg, bent knee, 3 s lowering (soleus)."),
              _acc("Cable Wood Chopper", 2, "10/side", acc_rpe, "45 s", "Anti-rotation core.", kind="core")]
    else:
        ex = [_acc("Broad Jump", 3, "4", None, "90 s", "Max distance, full reset between jumps. Power for hills and the swim start.", kind="prep"),
              _acc("ATG Split Squat", acc_sets, "8/leg", min(acc_rpe, 7), "superset", "Long run tomorrow: about 70% effort. Knee past toes, heel down.", 8, per="hand"),
              _acc("Seated Good Morning", acc_sets, "10", None, "90 s", "Superset with ATG split squat. Light: hip opener."),
              SHOULDER_PREP,
              _acc("Dips", acc_sets + (0 if rec else 1), "6-10", acc_rpe, "2 min", "Closed chain: shoulder-friendly. Slight forward lean.", 8, per="added"),
              _acc("Seated Cable Row", acc_sets, "10-12", acc_rpe, "90 s", "Full stretch at the front.", 10),
              _acc("Face Pull + Rear Delt Fly", acc_sets, "15 + 12", None, "60 s", "Superset. Third rear-delt dose of the week."),
              _acc("Dragon Flag", acc_sets, "5", acc_rpe, "60 s", "Tuck → straight over the weeks.", kind="core"),
              _acc("Hip mobility: pigeon, 90/90, CARs, couch stretch", 1, "6 min", None, "—", "Right hip first. Every Friday.", kind="mobility")]
    minutes = {"A": 60, "B": 55, "C": 50}[letter] - (10 if rec else 0) - (10 if phase in ("build", "peak", "taper") else 0)
    title = f"Full Body {letter}"
    return {"id": f"w{wn}-strength-{letter.lower()}", "sport": "strength", "type": "strength", "name": title,
            "description": label, "durationMinutes": minutes, "primaryZone": f"RPE {rpe:g}", "slot": "PM",
            "humanReadable": "\n".join(f"{e['name']}: {e['sets']}×{e['reps']}" + (f" @ RPE {e['rpe']:g}" if e.get("rpe") else "") for e in ex),
            "completed": False, "letter": letter, "scheme": {"sets": sets, "reps": reps, "rpe": rpe, "label": label},
            "exercises": [dict(e) for e in ex]}


# --------------------------------------------------------------------------- the program


def build(settings: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every week from the start date to race day (pure: depends only on settings and body data)."""
    settings = settings or load_settings()
    start = _monday(date.fromisoformat(settings["start_date"]))
    race = date.fromisoformat(settings["race_date"])
    n = (_monday(race) - start).days // 7 + 1
    layout = phase_layout(n)
    hours = settings["weekly_hours"]
    weeks = []
    for ph in layout:
        key = ph["key"]
        length = ph["endWeek"] - ph["startWeek"] + 1
        load_i = 0
        for j in range(length):
            wn = ph["startWeek"] + j
            rec = key in ("base1", "base2", "build") and (j + 1) % 4 == 0
            week1 = wn == 1
            lo, hi = RAMP.get(key, (0.6, 0.6))
            load_weeks = max(1, length - length // 4 - 1)
            p = min(1.0, load_i / load_weeks) if key in RAMP else 0.0
            f = {"taper": [0.7, 0.5][min(j, 1)], "race": 0.35}.get(key, lo + (hi - lo) * p)
            if week1:
                f = 0.7
            if rec:
                f *= RECOVERY_FACTOR
            ws = start + timedelta(weeks=wn - 1)
            dates = [ws + timedelta(days=k) for k in range(7)]
            by_day = _endurance(key, load_i, p, f, rec, week1, dates, settings, wn)
            letters = {"base1": "ABC", "base2": "ABC", "build": "AB", "peak": "AB", "taper": "A" if j == 0 else "", "race": ""}[key]
            lift_days = {"ABC": (0, 2, 4), "AB": (0, 2), "A": (0,), "": ()}[letters]
            for letter, day in zip(letters, lift_days):
                by_day[day].append(strength_session(letter, key, load_i, rec, week1, wn, wn))
            days = []
            for k, d in enumerate(dates):
                wos = sorted(by_day[k], key=lambda w: w["slot"])
                if not wos:
                    wos = [{"id": f"w{wn}-{DAYS[k][:3].lower()}-rest", "sport": "rest", "type": "rest", "name": "Rest",
                            "description": "Calf eccentrics (3×15 straight + 3×15 bent knee), right-hip routine, left-shoulder wall slides.",
                            "durationMinutes": 0, "humanReadable": "Full rest. Walk if you like.", "completed": False, "slot": "AM"}]
                days.append({"date": str(d), "dayOfWeek": DAYS[k], "workouts": wos})
            if key not in ("taper", "race") and not week1:
                _fit_to_hours(days, hours * f)
            by_sport: dict[str, dict[str, float]] = {}
            for d in days:
                for w in d["workouts"]:
                    if w["sport"] in ("rest", "race"):
                        continue
                    b = by_sport.setdefault(w["sport"], {"sessions": 0, "hours": 0.0})
                    b["sessions"] += 1
                    b["hours"] = round(b["hours"] + w["durationMinutes"] / 60, 2)
            total = round(sum(b["hours"] for b in by_sport.values()), 1)
            weeks.append({
                "weekNumber": wn, "startDate": str(dates[0]), "endDate": str(dates[6]), "phase": ph["name"], "phaseKey": key,
                "focus": "Tests and calibration" if week1 else ("Recovery week" if rec else ph["focus"].split(":")[0]),
                "targetHours": round(hours * f, 1), "isRecoveryWeek": rec, "days": days,
                "summary": {"totalHours": total, "bySport": by_sport},
            })
            if not rec and not week1:  # the test week does not count as a load week
                load_i += 1
    return {
        "version": "1.0",
        "meta": {"id": f"703-{settings['race_date']}", "event": settings["race_name"], "eventDate": settings["race_date"],
                 "planStartDate": str(start), "planEndDate": settings["race_date"], "totalWeeks": n, "generatedBy": "Claude Coach"},
        "preferences": {"swim": "meters", "bike": "kilometers", "run": "kilometers", "firstDayOfWeek": "monday"},
        "assessment": assessment(body),
        "zones": zones(settings, (body or {}).get("max_heart_rate")),
        "phases": layout,
        "weeks": weeks,
        "raceStrategy": race_strategy(settings),
    }


def assessment(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    return {
        "foundation": {"raceHistory": ["Ohrid aquathlon, Aug 2026 (500 m swim + 3 km run)"], "foundationLevel": "intermediate",
                       "yearsInSport": 1, "peakTrainingLoad": "about 70 km running a month (May-June 2026), 3 lifts a week"},
        "currentForm": {"asOf": "2026-11-02", "weeklyVolume": {"total": 4.75, "swim": 1.8, "bike": 0, "run": 0.5, "strength": 2.5},
                        "consistency": "2 weeks back after illness; recovery and HRV back to baseline",
                        "body": {k: body.get(k) for k in ("weight_kilogram", "height_meter", "max_heart_rate")}},
        "strengths": [{"sport": "strength", "evidence": "Years of 3 sessions a week; full-body A/B/C"},
                      {"sport": "run", "evidence": "Built to ~70 km a month this spring with mostly easy HR"}],
        "limiters": [{"sport": "bike", "evidence": "1-2 h of riding a month all year; no road bike yet"},
                     {"sport": "swim", "evidence": "Open-water beginner in June; longest continuous swim about 500 m"}],
        "constraints": ["Gym bike until a road bike arrives", "Pool Nov-May, Lake Ohrid from June",
                        "Left shoulder twinges: shoulder protocol + dumbbell pressing first", "Right hip: daily routine"],
    }


def race_strategy(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": {"name": settings["race_name"], "date": settings["race_date"], "type": "70.3",
                  "distances": {"swim": 1900, "bike": 90, "run": 21.1}},
        "pacing": {
            "swim": {"target": "CSS + 5-8 s/100 m", "notes": "First 200 m controlled; sight every 6-8 strokes."},
            "bike": {"targetHR": "Z2-low Z3 (under 90% of bike LTHR)", "notes": "Ride the first 30 min easier than it feels; the run is decided here."},
            "run": {"targetHR": "Z3 (90-93% of run LTHR)", "notes": "First 5 km at the bottom of the zone, walk aid stations if needed, push the last 5 km."},
        },
        "nutrition": {"preRace": "3 h before: 100-150 g carbs, low fibre, 500 ml fluid",
                      "during": {"carbsPerHour": 70, "fluidPerHour": "500-750 ml", "products": ["Practise the race-day gels and drink in long rides"]},
                      "notes": "Train the gut: every long ride from Base 2 at 60-80 g carbs per hour."},
        "taper": {"volumeReduction": 40, "notes": "Two weeks: volume down, short race-pace efforts stay."},
    }


# --------------------------------------------------------------------------- loads from the log


def estimated_maxes(sessions: list[dict[str, Any]], exercises: list[dict[str, Any]], body_kg: float | None,
                    today: date, window_days: int = 56) -> dict[str, dict[str, Any]]:
    """Best recent e1RM per exercise name from logged sets (RPE-aware), bodyweight added for bodyweight lifts."""
    by_id = {e["id"]: e for e in exercises}
    since = today - timedelta(days=window_days)
    best: dict[str, dict[str, Any]] = {}
    for sess in sessions:
        if date.fromisoformat(sess["date"]) < since:
            continue
        for s in sess["sets"]:
            ex = by_id.get(s["exercise_id"])
            if not ex or s["warmup"]:
                continue
            load = s["weight_kg"] + ((body_kg or 0) if ex["bodyweight"] else 0)
            est = e1rm(load, s["reps"], s.get("rpe"))
            if est and est > best.get(ex["name"], {}).get("e1rm", 0):
                best[ex["name"]] = {"e1rm": est, "date": sess["date"], "from": f"{s['weight_kg']:g} kg × {s['reps']}"
                                    + (f" @ RPE {s['rpe']:g}" if s.get("rpe") else ""), "bodyweight": ex["bodyweight"]}
    return best


def fill_loads(week: dict[str, Any], maxes: dict[str, dict[str, Any]], exercise_ids: dict[str, int], body_kg: float | None) -> None:
    """Add today's target kg to every strength exercise with reps and an RPE, from its estimated 1RM."""
    for day in week["days"]:
        for w in day["workouts"]:
            for e in w.get("exercises", []):
                e["exercise_id"] = exercise_ids.get(e["name"].lower())
                m = maxes.get(e["name"])
                if not (m and e.get("reps_n") and e.get("rpe")):
                    e["load"] = None
                    continue
                target = m["e1rm"] * pct_1rm(e["reps_n"], e["rpe"])
                if m["bodyweight"]:
                    added = target - (body_kg or 0)
                    e["load"] = {"kg": max(0.0, round_load(added, 1.25)), "per": "added", "e1rm": m["e1rm"],
                                 "note": "bodyweight" if added <= 0 else None}
                else:
                    step = 2.0 if e["per"] == "hand" else 2.5
                    e["load"] = {"kg": round_load(target, step), "per": e["per"], "e1rm": m["e1rm"], "note": None}


def mark_done(program: dict[str, Any], workouts: list[dict[str, Any]], strength_dates: set[str], today: date) -> None:
    """Tick sessions up to today that a WHOOP workout of the same sport (or a logged lift) covered that day."""
    by_day: dict[str, list[dict[str, Any]]] = {}
    for w in workouts:
        by_day.setdefault(w["date"], []).append(w)
    for week in program["weeks"]:
        if week["startDate"] > str(today):
            break
        for day in week["days"]:
            if day["date"] > str(today):
                break
            pool = list(by_day.get(day["date"], []))
            for w in day["workouts"]:
                if w["sport"] in ("rest", "race"):
                    continue
                match = next((x for x in pool if x["discipline"] == w["sport"]), None)
                if match:
                    pool.remove(match)
                w["completed"] = match is not None or (w["sport"] == "strength" and day["date"] in strength_dates)
                if match:
                    w["doneMinutes"] = match.get("duration_min")

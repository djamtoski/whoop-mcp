"""Strength log: exercises, sessions and sets in a local SQLite file (shared by MCP + dashboard).

WHOOP's API and data export carry no exercise-level data, so sets/reps/weights are logged here
and each session can be linked to the WHOOP workout it belongs to (for strain and heart rate).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any

from . import config

MUSCLES = ("quads", "glutes", "hamstrings", "calves", "chest", "shoulders", "triceps", "back", "biceps", "core")
PATTERNS = ("squat", "hinge", "lunge", "push", "pull", "carry", "core", "other")

# (name, pattern, primary muscles (first is the main one), push/pull/none, upper/lower/core, bodyweight)
LIBRARY: list[tuple[str, str, tuple[str, ...], str, str, bool]] = [
    ("Back Squat", "squat", ("quads", "glutes", "core"), "none", "lower", False),
    ("Front Squat", "squat", ("quads", "glutes", "core"), "none", "lower", False),
    ("Goblet Squat", "squat", ("quads", "glutes"), "none", "lower", False),
    ("Leg Press", "squat", ("quads", "glutes"), "none", "lower", False),
    ("Bulgarian Split Squat", "lunge", ("quads", "glutes"), "none", "lower", False),
    ("Walking Lunge", "lunge", ("quads", "glutes"), "none", "lower", False),
    ("Deadlift", "hinge", ("hamstrings", "glutes", "back"), "pull", "lower", False),
    ("Romanian Deadlift", "hinge", ("hamstrings", "glutes"), "pull", "lower", False),
    ("Hip Thrust", "hinge", ("glutes", "hamstrings"), "none", "lower", False),
    ("Kettlebell Swing", "hinge", ("glutes", "hamstrings"), "none", "lower", False),
    ("Calf Raise", "other", ("calves",), "none", "lower", False),
    ("Bench Press", "push", ("chest", "triceps", "shoulders"), "push", "upper", False),
    ("Incline Dumbbell Press", "push", ("chest", "shoulders", "triceps"), "push", "upper", False),
    ("Overhead Press", "push", ("shoulders", "triceps"), "push", "upper", False),
    ("Dips", "push", ("chest", "triceps"), "push", "upper", True),
    ("Push-up", "push", ("chest", "triceps"), "push", "upper", True),
    ("Barbell Row", "pull", ("back", "biceps"), "pull", "upper", False),
    ("Seated Cable Row", "pull", ("back", "biceps"), "pull", "upper", False),
    ("Pull-up", "pull", ("back", "biceps"), "pull", "upper", True),
    ("Lat Pulldown", "pull", ("back", "biceps"), "pull", "upper", False),
    ("Face Pull", "pull", ("shoulders", "back"), "pull", "upper", False),
    ("Plank", "core", ("core",), "none", "core", True),
    ("Pallof Press", "core", ("core",), "none", "core", False),
    ("Farmer Carry", "carry", ("core", "back"), "none", "core", False),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pattern TEXT NOT NULL,
    muscles TEXT NOT NULL,          -- JSON list, main muscle first
    push_pull TEXT NOT NULL,        -- push | pull | none
    region TEXT NOT NULL,           -- upper | lower | core
    bodyweight INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    whoop_workout_id TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sets (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    position INTEGER NOT NULL,
    reps INTEGER NOT NULL,
    weight_kg REAL NOT NULL DEFAULT 0,   -- added load for bodyweight exercises
    rpe REAL,
    warmup INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS sets_session ON sets(session_id);
CREATE INDEX IF NOT EXISTS sessions_date ON sessions(date);
"""


@contextmanager
def connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.STRENGTH_DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        con.executescript(SCHEMA)
        if not con.execute("SELECT 1 FROM exercises LIMIT 1").fetchone():
            con.executemany(
                "INSERT INTO exercises (name, pattern, muscles, push_pull, region, bodyweight) VALUES (?, ?, ?, ?, ?, ?)",
                [(n, p, json.dumps(list(m)), pp, r, int(bw)) for n, p, m, pp, r, bw in LIBRARY])
        yield con
        con.commit()
    finally:
        con.close()


def _exercise(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["id"], "name": row["name"], "pattern": row["pattern"], "muscles": json.loads(row["muscles"]),
            "push_pull": row["push_pull"], "region": row["region"], "bodyweight": bool(row["bodyweight"])}


def list_exercises() -> list[dict[str, Any]]:
    with connect() as con:
        return [_exercise(r) for r in con.execute("SELECT * FROM exercises ORDER BY name")]


def add_exercise(name: str, pattern: str, muscles: list[str], push_pull: str = "none",
                 region: str | None = None, bodyweight: bool = False) -> dict[str, Any]:
    name = " ".join((name or "").split())[:60]
    if not name:
        raise ValueError("exercise name is empty")
    if pattern not in PATTERNS:
        raise ValueError(f"pattern must be one of {', '.join(PATTERNS)}")
    bad = [m for m in muscles if m not in MUSCLES]
    if not muscles or bad:
        raise ValueError(f"muscles must be a non-empty list from {', '.join(MUSCLES)}")
    if push_pull not in ("push", "pull", "none"):
        raise ValueError("push_pull must be push, pull or none")
    region = region or ("lower" if muscles[0] in ("quads", "glutes", "hamstrings", "calves")
                        else "core" if muscles[0] == "core" else "upper")
    if region not in ("upper", "lower", "core"):
        raise ValueError("region must be upper, lower or core")
    with connect() as con:
        try:
            cur = con.execute(
                "INSERT INTO exercises (name, pattern, muscles, push_pull, region, bodyweight) VALUES (?, ?, ?, ?, ?, ?)",
                (name, pattern, json.dumps(muscles), push_pull, region, int(bodyweight)))
        except sqlite3.IntegrityError:
            raise ValueError(f"an exercise called {name!r} already exists") from None
        return _exercise(con.execute("SELECT * FROM exercises WHERE id = ?", (cur.lastrowid,)).fetchone())


def find_exercise(con: sqlite3.Connection, ref: int | str) -> sqlite3.Row:
    row = (con.execute("SELECT * FROM exercises WHERE id = ?", (ref,)).fetchone() if isinstance(ref, int)
           else con.execute("SELECT * FROM exercises WHERE name = ?", (str(ref).strip(),)).fetchone())
    if row is None:
        raise ValueError(f"unknown exercise {ref!r}")
    return row


def _clean_sets(con: sqlite3.Connection, sets: list[dict[str, Any]]) -> list[tuple]:
    if not sets:
        raise ValueError("a session needs at least one set")
    out = []
    for i, s in enumerate(sets):
        ex = find_exercise(con, s.get("exercise_id") or s.get("exercise") or "")
        reps = int(s.get("reps") or 0)
        kg = float(s.get("weight_kg") or 0)
        rpe = s.get("rpe")
        if not 0 < reps <= 100:
            raise ValueError(f"set {i + 1}: reps must be 1-100")
        if not 0 <= kg <= 500:
            raise ValueError(f"set {i + 1}: weight_kg must be 0-500")
        if rpe is not None and not 1 <= float(rpe) <= 10:
            raise ValueError(f"set {i + 1}: rpe must be 1-10")
        out.append((ex["id"], i, reps, kg, None if rpe is None else float(rpe), int(bool(s.get("warmup")))))
    return out


def save_session(day: str, sets: list[dict[str, Any]], notes: str = "", whoop_workout_id: str | None = None,
                 session_id: int | None = None) -> dict[str, Any]:
    """Create a session, or replace one (its sets too) when session_id is given."""
    date.fromisoformat(day)  # validates
    with connect() as con:
        rows = _clean_sets(con, sets)
        if session_id is None:
            cur = con.execute("INSERT INTO sessions (date, whoop_workout_id, notes, created_at) VALUES (?, ?, ?, ?)",
                              (day, whoop_workout_id or None, (notes or "")[:2000], datetime.now(timezone.utc).isoformat()))
            session_id = cur.lastrowid
        else:
            if not con.execute("UPDATE sessions SET date = ?, whoop_workout_id = ?, notes = ? WHERE id = ?",
                               (day, whoop_workout_id or None, (notes or "")[:2000], session_id)).rowcount:
                raise ValueError(f"no session {session_id}")
            con.execute("DELETE FROM sets WHERE session_id = ?", (session_id,))
        con.executemany("INSERT INTO sets (session_id, exercise_id, position, reps, weight_kg, rpe, warmup) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [(session_id, *r) for r in rows])
    return get_session(session_id)


def delete_session(session_id: int) -> bool:
    with connect() as con:
        return con.execute("DELETE FROM sessions WHERE id = ?", (session_id,)).rowcount > 0


def _sessions(con: sqlite3.Connection, where: str = "", args: tuple = ()) -> list[dict[str, Any]]:
    sess = [dict(r) for r in con.execute(f"SELECT * FROM sessions {where} ORDER BY date DESC, id DESC", args)]
    if not sess:
        return []
    ids = [s["id"] for s in sess]
    q = ("SELECT sets.*, exercises.name AS exercise FROM sets JOIN exercises ON exercises.id = sets.exercise_id "
         f"WHERE session_id IN ({','.join('?' * len(ids))}) ORDER BY position")
    by: dict[int, list[dict[str, Any]]] = {i: [] for i in ids}
    for r in con.execute(q, ids):
        by[r["session_id"]].append({"exercise_id": r["exercise_id"], "exercise": r["exercise"], "reps": r["reps"],
                                    "weight_kg": r["weight_kg"], "rpe": r["rpe"], "warmup": bool(r["warmup"])})
    for s in sess:
        s["sets"] = by[s["id"]]
    return sess


def get_session(session_id: int) -> dict[str, Any]:
    with connect() as con:
        found = _sessions(con, "WHERE id = ?", (session_id,))
    if not found:
        raise ValueError(f"no session {session_id}")
    return found[0]


def list_sessions(since: str | None = None) -> list[dict[str, Any]]:
    with connect() as con:
        return _sessions(con, "WHERE date >= ?", (since,)) if since else _sessions(con)

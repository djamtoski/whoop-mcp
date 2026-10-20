"""Full-history export (WHOOP API) and import of the WHOOP app's CSV data export."""

from __future__ import annotations

import csv
import json
import shutil
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from . import analytics as an
from . import config
from .client import WhoopClient

# The API's `start` is inclusive; WHOOP launched in 2015, so this covers any account.
HISTORY_START = datetime(2012, 1, 1, tzinfo=timezone.utc)
COLLECTIONS = {
    "cycles": "/v2/cycle",
    "recoveries": "/v2/recovery",
    "sleeps": "/v2/activity/sleep",
    "workouts": "/v2/activity/workout",
}


def default_export_root() -> Path:
    if (config.PROJECT_ROOT / "pyproject.toml").exists():
        return config.PROJECT_ROOT / "exports"
    return config.DATA_DIR / "exports"


def _log(msg: str) -> None:
    # stderr: this also runs inside the stdio MCP server, where stdout is the protocol channel.
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- flattening

def flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, f"{key}."))
        elif isinstance(v, list):
            out[key] = json.dumps(v)
        else:
            out[key] = v
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    flat = [flatten(r) for r in rows]
    cols: list[str] = []
    for r in flat:
        for k in r:
            if k not in cols:
                cols.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(flat)


# --------------------------------------------------------------------------- summaries

def _avg(xs) -> float | None:
    vals = [x for x in xs if isinstance(x, (int, float))]
    return round(mean(vals), 1) if vals else None


def monthly_summary(raw: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    table = an.daily_table(raw["cycles"], raw["recoveries"], raw["sleeps"], raw["workouts"])
    months: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for day, row in table.items():
        m = months[day.strftime("%Y-%m")]
        rec = an.scored(row.get("recovery"))
        m["recovery"].append(rec.get("recovery_score"))
        m["hrv"].append(rec.get("hrv_rmssd_milli"))
        m["rhr"].append(rec.get("resting_heart_rate"))
        m["strain"].append(an.scored(row.get("cycle")).get("strain"))
        if row.get("sleep"):
            s = an.summarize_sleep(row["sleep"])
            m["sleep_h"].append(s["hours_asleep"])
            m["sleep_perf"].append(s["performance_pct"])
        for w in row["workouts"]:
            ws = an.summarize_workout(w)
            m[f"min_{ws['discipline']}"].append(ws["duration_min"] or 0)
            m[f"km_{ws['discipline']}"].append(ws["distance_km"] or 0)
    out = []
    for month in sorted(months):
        m = months[month]
        disciplines = sorted({k[4:] for k in m if k.startswith("min_")})
        out.append({
            "month": month,
            "days_with_recovery": sum(1 for x in m["recovery"] if x is not None),
            "avg_recovery": _avg(m["recovery"]),
            "avg_hrv_ms": _avg(m["hrv"]),
            "avg_rhr": _avg(m["rhr"]),
            "avg_day_strain": _avg(m["strain"]),
            "avg_sleep_h": _avg(m["sleep_h"]),
            "avg_sleep_performance": _avg(m["sleep_perf"]),
            "training": {d: {"sessions": len(m[f"min_{d}"]),
                             "hours": round(sum(m[f"min_{d}"]) / 60, 1),
                             "km": round(sum(m[f"km_{d}"]), 1)} for d in disciplines},
        })
    return out


def _span(records: list[dict[str, Any]], field: str = "start") -> list[str | None]:
    vals = sorted(r.get(field) or "" for r in records if r.get(field))
    return [vals[0][:10], vals[-1][:10]] if vals else [None, None]


# --------------------------------------------------------------------------- API export

async def export_history(out_root: Path | None = None, client: WhoopClient | None = None) -> dict[str, Any]:
    out_root = out_root or default_export_root()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out = out_root / stamp
    out.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or WhoopClient()
    raw: dict[str, list[dict[str, Any]]] = {}
    try:
        # Sequential, throttled: WHOOP rate-limits per app (~100 requests/minute).
        for name, path in COLLECTIONS.items():
            _log(f"Fetching {name}...")
            raw[name] = await client.history(
                path, HISTORY_START,
                on_page=lambda n, name=name: _log(f"  {name}: {n} records") if n % 250 == 0 else None)
            _log(f"  {name}: {len(raw[name])} records")
        profile = await client.profile()
        try:
            body = await client.body()
        except Exception:  # noqa: BLE001 - scope may be missing
            body = None
    finally:
        if own_client:
            await client.aclose()

    (out / "raw").mkdir(exist_ok=True)
    for name, recs in raw.items():
        (out / "raw" / f"{name}.json").write_text(json.dumps(recs, indent=1), encoding="utf-8")
        write_csv(out / f"{name}.csv", recs)
    (out / "raw" / "profile.json").write_text(json.dumps({"profile": profile, "body": body}, indent=1), encoding="utf-8")

    # Friendlier, unit-converted tables (hours, minutes, km) alongside the raw columns.
    write_csv(out / "sleeps_summary.csv", [an.summarize_sleep(s) for s in raw["sleeps"]])
    write_csv(out / "workouts_summary.csv", [an.summarize_workout(w) for w in raw["workouts"]])
    months = monthly_summary(raw)
    write_csv(out / "monthly_summary.csv", months)

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "directory": str(out),
        "counts": {k: len(v) for k, v in raw.items()},
        "date_range": {"cycles": _span(raw["cycles"]), "sleeps": _span(raw["sleeps"]),
                       "workouts": _span(raw["workouts"]), "recoveries": _span(raw["recoveries"], "created_at")},
        "body": body,
        "files": sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()),
        "monthly_summary": months,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (out_root / "LATEST").write_text(stamp, encoding="utf-8")
    return manifest


def latest_export() -> Path | None:
    root = default_export_root()
    try:
        p = root / (root / "LATEST").read_text(encoding="utf-8").strip()
        return p if p.is_dir() else None
    except FileNotFoundError:
        return None


# --------------------------------------------------------------------------- app export import

def import_app_export(zip_path: Path, export_dir: Path | None = None) -> dict[str, Any]:
    """Unpack the CSV ZIP from WHOOP app > Settings > Data Export into an export folder.

    Only .csv members are extracted, by basename (no path traversal).
    """
    export_dir = export_dir or latest_export() or (default_export_root() / datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    dest = export_dir / "app_export"
    dest.mkdir(parents=True, exist_ok=True)
    found: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if info.is_dir() or not name.lower().endswith(".csv"):
                continue
            target = dest / name
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            with target.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, [])
                rows = sum(1 for _ in reader)
            found[name] = {"rows": rows, "columns": header}
    return {"directory": str(dest), "files": found}

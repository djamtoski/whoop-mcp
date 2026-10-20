"""Pure analytics over raw WHOOP v2 records (no I/O, easily testable).

Fields the public API does not expose directly are derived here and marked as such:
  * stress score   -> `stress_estimate` (HRV/RHR deviation from 7-day baseline, 0–3)
  * target strain  -> `target_strain` (heuristic band from recovery)
  * rolling sleep debt -> sum of (need - actual) over recent nights
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any, Iterable

Record = dict[str, Any]

MS_PER_H = 3_600_000


# --------------------------------------------------------------------------- helpers

def _num(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) else None


def _r(x: float | None, nd: int = 1) -> float | None:
    return None if x is None else round(x, nd)


def ms_to_h(ms: Any) -> float | None:
    v = _num(ms)
    return None if v is None else round(v / MS_PER_H, 2)


def _mean(xs: Iterable[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return mean(vals) if vals else None


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _tz(offset: str | None) -> timezone:
    if not offset:
        return timezone.utc
    sign = -1 if offset.startswith("-") else 1
    hh, _, mm = offset.lstrip("+-").partition(":")
    return timezone(sign * timedelta(hours=int(hh or 0), minutes=int(mm or 0)))


def local_dt(rec: Record, field: str) -> datetime | None:
    dt = _parse_ts(rec.get(field))
    return dt.astimezone(_tz(rec.get("timezone_offset"))) if dt else None


def _duration_s(rec: Record) -> float:
    start, end = _parse_ts(rec.get("start")), _parse_ts(rec.get("end"))
    return (end - start).total_seconds() if start and end else 0.0


def cycle_day(cycle: Record) -> date | None:
    """A cycle starts at sleep onset; +6h maps late-night starts to the waking day."""
    dt = local_dt(cycle, "start")
    return (dt + timedelta(hours=6)).date() if dt else None


def sleep_day(sleep: Record) -> date | None:
    dt = local_dt(sleep, "end") or local_dt(sleep, "start")
    return dt.date() if dt else None


def workout_day(w: Record) -> date | None:
    dt = local_dt(w, "start")
    return dt.date() if dt else None


def scored(rec: Record | None) -> dict[str, Any]:
    if not rec or rec.get("score_state") not in (None, "SCORED"):
        return {}
    return rec.get("score") or {}


def parse_day(value: str | None, today: date | None = None) -> date:
    today = today or date.today()
    if not value or value.lower() in ("today", "now"):
        return today
    if value.lower() == "yesterday":
        return today - timedelta(days=1)
    return date.fromisoformat(value)


# --------------------------------------------------------------------------- classification

def readiness_zone(score: float | None) -> str | None:
    if score is None:
        return None
    return "green" if score >= 67 else "yellow" if score >= 34 else "red"


def target_strain(recovery_score: float | None) -> dict[str, Any] | None:
    """Heuristic optimal day-strain band for a triathlete given recovery (not a WHOOP field)."""
    if recovery_score is None:
        return None
    if recovery_score >= 67:
        lo, hi, focus = 14.0, 18.0, "Quality/threshold or long session is well supported."
    elif recovery_score >= 34:
        lo, hi, focus = 10.0, 14.0, "Aerobic/tempo work; keep intensity controlled."
    else:
        lo, hi, focus = 6.0, 10.0, "Recovery day: Z1–Z2 only, technique swim or easy spin."
    return {"low": lo, "high": hi, "guidance": focus, "derived": True}


SPORT_KEYWORDS = {
    "swim": ("swim",),
    "bike": ("cycl", "bik", "spin", "peloton", "zwift"),
    "run": ("run", "track", "jog", "sprint"),
    "tri": ("triathlon", "duathlon"),
    "strength": ("weight", "strength", "functional", "lift", "crossfit", "bodybuild", "powerlift"),
    # Not training load: logged for completeness but kept out of swim/bike/run volume.
    "recovery": ("meditat", "stretch", "sauna", "yoga", "mobility", "breathwork", "massage", "ice bath", "cold"),
}


def classify_sport(sport_name: str | None) -> str:
    name = (sport_name or "").lower()
    if "triathlon" in name or "duathlon" in name:
        return "tri"
    for discipline, keys in SPORT_KEYWORDS.items():
        if any(k in name for k in keys):
            return discipline
    return "other"


def stress_estimate(hrv: float | None, hrv_base: float | None,
                    rhr: float | None, rhr_base: float | None) -> dict[str, Any] | None:
    """0–3 physiological stress proxy: 10% HRV suppression ≈ 1 pt, 5% RHR elevation ≈ 1 pt."""
    if None in (hrv, hrv_base, rhr, rhr_base) or not hrv_base or not rhr_base:
        return None
    hrv_drop = max(0.0, (hrv_base - hrv) / hrv_base)
    rhr_rise = max(0.0, (rhr - rhr_base) / rhr_base)
    score = min(3.0, hrv_drop * 10 + rhr_rise * 20)
    level = "low" if score < 1 else "medium" if score < 2 else "high"
    return {"score": round(score, 2), "level": level, "derived": True}


# --------------------------------------------------------------------------- summaries

def summarize_sleep(s: Record) -> dict[str, Any]:
    sc = scored(s)
    st = sc.get("stage_summary") or {}
    need = sc.get("sleep_needed") or {}
    in_bed = _num(st.get("total_in_bed_time_milli")) or 0
    awake = _num(st.get("total_awake_time_milli")) or 0
    no_data = _num(st.get("total_no_data_time_milli")) or 0
    actual_ms = max(0.0, in_bed - awake - no_data) if st else None
    need_ms = sum(_num(need.get(k)) or 0 for k in (
        "baseline_milli", "need_from_sleep_debt_milli",
        "need_from_recent_strain_milli", "need_from_recent_nap_milli")) if need else None
    return {
        "id": s.get("id"),
        "date": str(sleep_day(s)),
        "start": s.get("start"),
        "end": s.get("end"),
        "nap": bool(s.get("nap")),
        "score_state": s.get("score_state"),
        "performance_pct": _num(sc.get("sleep_performance_percentage")),
        "efficiency_pct": _r(_num(sc.get("sleep_efficiency_percentage"))),
        "consistency_pct": _num(sc.get("sleep_consistency_percentage")),
        "respiratory_rate": _r(_num(sc.get("respiratory_rate"))),
        "hours_in_bed": ms_to_h(in_bed) if st else None,
        "hours_asleep": ms_to_h(actual_ms),
        "hours_needed": ms_to_h(need_ms),
        "need_breakdown_h": {
            "baseline": ms_to_h(need.get("baseline_milli")),
            "from_sleep_debt": ms_to_h(need.get("need_from_sleep_debt_milli")),
            "from_strain": ms_to_h(need.get("need_from_recent_strain_milli")),
            "from_naps": ms_to_h(need.get("need_from_recent_nap_milli")),
        } if need else None,
        "awakenings": st.get("disturbance_count"),
        "sleep_cycles": st.get("sleep_cycle_count"),
        "stages_h": {
            "deep_sws": ms_to_h(st.get("total_slow_wave_sleep_time_milli")),
            "rem": ms_to_h(st.get("total_rem_sleep_time_milli")),
            "light": ms_to_h(st.get("total_light_sleep_time_milli")),
            "awake": ms_to_h(st.get("total_awake_time_milli")),
        } if st else None,
    }


def summarize_workout(w: Record) -> dict[str, Any]:
    sc = scored(w)
    zones = sc.get("zone_durations") or {}
    start, end = _parse_ts(w.get("start")), _parse_ts(w.get("end"))
    names = ["zone_zero_milli", "zone_one_milli", "zone_two_milli",
             "zone_three_milli", "zone_four_milli", "zone_five_milli"]
    zone_min = {f"z{i}": round((_num(zones.get(n)) or 0) / 60000, 1) for i, n in enumerate(names)} if zones else None
    return {
        "id": w.get("id"),
        "date": str(workout_day(w)),
        "start": w.get("start"),
        "sport": w.get("sport_name"),
        "discipline": classify_sport(w.get("sport_name")),
        "duration_min": round((end - start).total_seconds() / 60, 1) if start and end else None,
        "strain": _r(_num(sc.get("strain"))),
        "avg_hr": sc.get("average_heart_rate"),
        "max_hr": sc.get("max_heart_rate"),
        "kilojoules": _r(_num(sc.get("kilojoule")), 0),
        "distance_km": _r((_num(sc.get("distance_meter")) or 0) / 1000, 2) if sc.get("distance_meter") else None,
        "altitude_gain_m": _r(_num(sc.get("altitude_gain_meter")), 0),
        "zone_minutes": zone_min,
    }


def summarize_cycle(c: Record) -> dict[str, Any]:
    sc = scored(c)
    return {
        "id": c.get("id"),
        "date": str(cycle_day(c)),
        "in_progress": c.get("end") is None,
        "day_strain": _r(_num(sc.get("strain"))),
        "kilojoules": _r(_num(sc.get("kilojoule")), 0),
        "avg_hr": sc.get("average_heart_rate"),
        "max_hr": sc.get("max_heart_rate"),
    }


# --------------------------------------------------------------------------- daily table

def daily_table(cycles: list[Record], recoveries: list[Record], sleeps: list[Record],
                workouts: list[Record]) -> dict[date, dict[str, Any]]:
    """Join records into one row per local day."""
    days: dict[date, dict[str, Any]] = defaultdict(lambda: {"workouts": []})
    cycle_by_id = {c.get("id"): c for c in cycles}
    for c in cycles:
        d = cycle_day(c)
        if d:
            days[d]["cycle"] = c
    for r in recoveries:
        c = cycle_by_id.get(r.get("cycle_id"))
        d = cycle_day(c) if c else None
        if d is None:
            created = _parse_ts(r.get("created_at"))
            d = created.date() if created else None
        if d:
            days[d]["recovery"] = r
    for s in sleeps:
        d = sleep_day(s)
        if d and not s.get("nap"):
            prev = days[d].get("sleep")
            # keep the longest main sleep ending on that day
            if prev is None or _duration_s(s) > _duration_s(prev):
                days[d]["sleep"] = s
    for w in workouts:
        d = workout_day(w)
        if d:
            days[d]["workouts"].append(w)
    return dict(days)


def _vitals(row: dict[str, Any]) -> dict[str, Any]:
    rec = scored(row.get("recovery"))
    slp = scored(row.get("sleep"))
    return {
        "recovery": _num(rec.get("recovery_score")),
        "hrv": _num(rec.get("hrv_rmssd_milli")),
        "rhr": _num(rec.get("resting_heart_rate")),
        "spo2": _num(rec.get("spo2_percentage")),
        "skin_temp": _num(rec.get("skin_temp_celsius")),
        "resp_rate": _num(slp.get("respiratory_rate")),
        "calibrating": rec.get("user_calibrating"),
    }


def baseline(table: dict[date, dict[str, Any]], day: date, key: str, n: int = 7) -> float | None:
    """Mean of `key` over the n days *before* `day`."""
    vals = [_vitals(table[d])[key] for d in (day - timedelta(days=i) for i in range(1, n + 1)) if d in table]
    return _mean(vals)


def recovery_report(table: dict[date, dict[str, Any]], day: date) -> dict[str, Any]:
    row = table.get(day)
    if not row or not row.get("recovery"):
        return {"date": str(day), "available": False,
                "message": "No scored recovery for this date yet (strap may still be processing sleep)."}
    v = _vitals(row)
    hrv_b, rhr_b = baseline(table, day, "hrv"), baseline(table, day, "rhr")
    skin_b, resp_b = baseline(table, day, "skin_temp"), baseline(table, day, "resp_rate")
    return {
        "date": str(day),
        "available": True,
        "score_state": row["recovery"].get("score_state"),
        "user_calibrating": v["calibrating"],
        "recovery_score": v["recovery"],
        "readiness_zone": readiness_zone(v["recovery"]),
        "hrv_rmssd_ms": _r(v["hrv"]),
        "hrv_baseline_7d_ms": _r(hrv_b),
        "hrv_vs_baseline_pct": _r((v["hrv"] - hrv_b) / hrv_b * 100) if v["hrv"] and hrv_b else None,
        "resting_hr": v["rhr"],
        "rhr_baseline_7d": _r(rhr_b),
        "rhr_vs_baseline_bpm": _r(v["rhr"] - rhr_b) if v["rhr"] and rhr_b else None,
        "spo2_pct": _r(v["spo2"]),
        "skin_temp_c": _r(v["skin_temp"], 2),
        "skin_temp_deviation_c": _r(v["skin_temp"] - skin_b, 2) if v["skin_temp"] and skin_b else None,
        "respiratory_rate": _r(v["resp_rate"]),
        "respiratory_rate_deviation": _r(v["resp_rate"] - resp_b, 2) if v["resp_rate"] and resp_b else None,
        "stress_estimate": stress_estimate(v["hrv"], hrv_b, v["rhr"], rhr_b),
        "target_strain": target_strain(v["recovery"]),
    }


def sleep_report(table: dict[date, dict[str, Any]], sleeps: list[Record], day: date,
                 debt_window: int = 7) -> dict[str, Any]:
    row = table.get(day) or {}
    main = row.get("sleep")
    naps = [summarize_sleep(s) for s in sleeps if s.get("nap") and sleep_day(s) == day]
    nights = []
    for i in range(debt_window):
        d = day - timedelta(days=i)
        s = (table.get(d) or {}).get("sleep")
        if s:
            ss = summarize_sleep(s)
            if ss["hours_needed"] is not None and ss["hours_asleep"] is not None:
                nights.append({"date": str(d), "needed_h": ss["hours_needed"], "asleep_h": ss["hours_asleep"],
                               "balance_h": round(ss["hours_asleep"] - ss["hours_needed"], 2)})
    nap_h = sum(n["hours_asleep"] or 0 for n in naps)
    rolling = round(max(0.0, -sum(n["balance_h"] for n in nights)), 2) if nights else None
    main_s = summarize_sleep(main) if main else None
    return {
        "date": str(day),
        "available": main is not None,
        "sleep": main_s,
        "naps": naps,
        "sleep_debt": {
            "whoop_debt_component_h": (main_s or {}).get("need_breakdown_h", {}).get("from_sleep_debt") if main_s and main_s.get("need_breakdown_h") else None,
            "tonight_shortfall_h": round(max(0.0, (main_s["hours_needed"] or 0) - (main_s["hours_asleep"] or 0) - nap_h), 2) if main_s and main_s["hours_needed"] else None,
            f"rolling_{debt_window}d_h": rolling,
            "nights": nights,
            "derived": True,
        },
    }


def strain_report(table: dict[date, dict[str, Any]], day: date, days_back: int) -> dict[str, Any]:
    days_out = []
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"sessions": 0, "minutes": 0.0, "kilojoules": 0.0, "distance_km": 0.0})
    for i in range(days_back):
        d = day - timedelta(days=i)
        row = table.get(d) or {"workouts": []}
        cyc = summarize_cycle(row["cycle"]) if row.get("cycle") else None
        wos = sorted((summarize_workout(w) for w in row["workouts"]), key=lambda w: w["start"] or "")
        for w in wos:
            t = totals[w["discipline"]]
            t["sessions"] += 1
            t["minutes"] += w["duration_min"] or 0
            t["kilojoules"] += w["kilojoules"] or 0
            t["distance_km"] += w["distance_km"] or 0
        rec = _vitals(row)["recovery"] if row.get("recovery") else None
        days_out.append({
            "date": str(d),
            "day_strain": cyc["day_strain"] if cyc else None,
            "in_progress": cyc["in_progress"] if cyc else None,
            "kilojoules": cyc["kilojoules"] if cyc else None,
            "recovery_score": rec,
            "target_strain": target_strain(rec),
            "workouts": wos,
        })
    return {
        "days": days_out,
        "discipline_totals": {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in totals.items()},
    }


def weekly_trends(table: dict[date, dict[str, Any]], day: date, days: int = 7) -> dict[str, Any]:
    series = []
    for i in reversed(range(days)):
        d = day - timedelta(days=i)
        row = table.get(d) or {}
        v = _vitals(row) if row else {}
        cyc = scored(row.get("cycle")) if row else {}
        slp = summarize_sleep(row["sleep"]) if row.get("sleep") else {}
        series.append({
            "date": str(d),
            "recovery": v.get("recovery"),
            "hrv": _r(v.get("hrv")),
            "rhr": v.get("rhr"),
            "day_strain": _r(_num(cyc.get("strain"))),
            "sleep_performance": slp.get("performance_pct"),
            "hours_asleep": slp.get("hours_asleep"),
            "hours_needed": slp.get("hours_needed"),
        })

    def avg(key, rows):
        return _r(_mean(r[key] for r in rows))

    prior = []
    for i in range(days, days * 4):
        d = day - timedelta(days=i)
        row = table.get(d)
        if row:
            v = _vitals(row)
            prior.append({"hrv": v["hrv"], "rhr": v["rhr"], "recovery": v["recovery"],
                          "day_strain": _num(scored(row.get("cycle")).get("strain"))})

    hrv7, rhr7, rec7, strain7 = avg("hrv", series), avg("rhr", series), avg("recovery", series), avg("day_strain", series)
    hrv28 = _r(_mean([r["hrv"] for r in series] + [p["hrv"] for p in prior]))
    rhr28 = _r(_mean([r["rhr"] for r in series] + [p["rhr"] for p in prior]))
    strain28 = _mean([r["day_strain"] for r in series] + [p["day_strain"] for p in prior])
    acwr = round(strain7 / strain28, 2) if strain7 and strain28 else None

    flags = []
    recent = [r for r in series[-4:] if r["hrv"] is not None]
    if hrv28 and sum(1 for r in recent if r["hrv"] < hrv28 * 0.9) >= 3:
        flags.append("HRV suppressed >10% below 28-day baseline on 3+ of last 4 days")
    if rhr28 and sum(1 for r in series[-4:] if r["rhr"] and r["rhr"] > rhr28 + 3) >= 2:
        flags.append("Resting HR elevated >3 bpm above baseline on 2+ recent days")
    reds = 0
    for r in reversed(series):
        if r["recovery"] is not None and r["recovery"] < 34:
            reds += 1
        else:
            break
    if reds >= 2:
        flags.append(f"{reds} consecutive red recovery days")
    if acwr and acwr > 1.3:
        flags.append(f"Acute:chronic strain ratio {acwr} (>1.3 raises injury/overreach risk)")
    sleep_deficit = sum((r["hours_needed"] or 0) - (r["hours_asleep"] or 0) for r in series if r["hours_needed"])
    if sleep_deficit > 5:
        flags.append(f"Cumulative 7-day sleep shortfall ≈ {sleep_deficit:.1f} h")

    def direction(cur, base, higher_good=True, tol=0.03):
        if cur is None or base is None or base == 0:
            return None
        delta = (cur - base) / base
        if abs(delta) < tol:
            return "stable"
        return "improving" if (delta > 0) == higher_good else "declining"

    return {
        "end_date": str(day),
        "series": series,
        "averages_7d": {"recovery": rec7, "hrv": hrv7, "rhr": rhr7, "day_strain": strain7,
                        "sleep_performance": avg("sleep_performance", series)},
        "baselines_28d": {"hrv": hrv28, "rhr": rhr28, "day_strain": _r(strain28)},
        "hrv_trend": direction(hrv7, hrv28),
        "rhr_trend": direction(rhr7, rhr28, higher_good=False),
        "acute_chronic_strain_ratio": acwr,
        "overtraining_flags": flags,
        "status": "caution" if len(flags) >= 2 else "watch" if flags else "ok",
    }

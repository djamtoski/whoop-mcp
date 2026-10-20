"""Deterministic synthetic WHOOP v2 records for demo mode and tests."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

TZ = "-05:00"
_tz = timezone(timedelta(hours=-5))


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


SESSIONS = [  # (sport_name, minutes, strain, avg_hr, max_hr, km)
    ("Swimming", 50, 9.8, 128, 156, 2.6),
    ("Cycling", 90, 13.4, 138, 171, 42.0),
    ("Running", 55, 12.1, 149, 178, 11.2),
    ("Cycling", 150, 15.6, 132, 165, 75.0),
    ("Running", 35, 8.2, 139, 158, 6.5),
    ("Swimming", 40, 8.9, 124, 150, 2.0),
    ("Functional Fitness", 40, 7.4, 118, 149, None),
]


def generate(end: date | None = None, days: int = 30, seed: int = 7) -> dict[str, list[dict[str, Any]]]:
    rnd = random.Random(seed)
    end = end or date.today()
    cycles, recs, sleeps, workouts = [], [], [], []
    for i in reversed(range(days)):
        d = end - timedelta(days=i)
        fatigue = 1.0 if i in (2, 3) else 0.0  # a dip two/three days ago
        onset = datetime.combine(d - timedelta(days=1), time(22, 40), _tz) + timedelta(minutes=rnd.randint(-40, 50))
        wake = onset + timedelta(hours=8.0 + rnd.uniform(-0.9, 0.7) - 0.8 * fatigue)
        cid = 1000 + (days - i)
        sid = f"00000000-0000-4000-8000-{cid:012d}"
        hrv = 78 + rnd.uniform(-9, 9) - 14 * fatigue
        rhr = 46 + rnd.uniform(-2, 2) + 3 * fatigue
        score = max(8, min(99, 60 + (hrv - 75) * 2.2 - (rhr - 46) * 3 + rnd.uniform(-8, 8)))
        in_bed = (wake - onset).total_seconds() * 1000
        awake = in_bed * rnd.uniform(0.05, 0.11)
        sleep_ms = in_bed - awake
        need = 8.1 * 3_600_000
        debt = max(0, 0.6 - 0.3 * rnd.random()) * 3_600_000
        is_today = i == 0
        cycle_end = None if is_today else wake + timedelta(hours=15.5)
        sess = [SESSIONS[(days - i) % len(SESSIONS)]]
        if (days - i) % 3 == 0:
            sess.append(SESSIONS[(days - i + 3) % len(SESSIONS)])
        if (days - i) % 7 == 0:
            sess = []
        strains = sorted((s[2] for s in sess), reverse=True)
        day_strain = min(20.5, 4.5 + (strains[0] * 0.75 if strains else 0) + sum(strains[1:]) * 0.3 + rnd.uniform(-0.6, 0.6))
        cycles.append({
            "id": cid, "user_id": 1, "start": _iso(onset), "end": _iso(cycle_end) if cycle_end else None,
            "timezone_offset": TZ, "score_state": "SCORED",
            "score": {"strain": round(day_strain * (0.55 if is_today else 1), 2), "kilojoule": round(7000 + day_strain * 350),
                      "average_heart_rate": 66, "max_heart_rate": 172},
        })
        recs.append({
            "cycle_id": cid, "sleep_id": sid, "user_id": 1, "created_at": _iso(wake),
            "updated_at": _iso(wake), "score_state": "SCORED",
            "score": {"user_calibrating": False, "recovery_score": round(score), "resting_heart_rate": round(rhr),
                      "hrv_rmssd_milli": round(hrv, 3), "spo2_percentage": round(96.5 + rnd.uniform(-1, 1.5), 2),
                      "skin_temp_celsius": round(33.6 + rnd.uniform(-0.3, 0.3) + 0.4 * fatigue, 2)},
        })
        sleeps.append({
            "id": sid, "cycle_id": cid, "user_id": 1, "start": _iso(onset), "end": _iso(wake),
            "timezone_offset": TZ, "nap": False, "score_state": "SCORED",
            "score": {
                "stage_summary": {
                    "total_in_bed_time_milli": round(in_bed), "total_awake_time_milli": round(awake),
                    "total_no_data_time_milli": 0,
                    "total_light_sleep_time_milli": round(sleep_ms * 0.5),
                    "total_slow_wave_sleep_time_milli": round(sleep_ms * 0.24),
                    "total_rem_sleep_time_milli": round(sleep_ms * 0.26),
                    "sleep_cycle_count": 4 + rnd.randint(0, 2), "disturbance_count": rnd.randint(3, 14),
                },
                "sleep_needed": {"baseline_milli": round(need - debt - 0.3 * 3_600_000),
                                 "need_from_sleep_debt_milli": round(debt),
                                 "need_from_recent_strain_milli": round(0.3 * 3_600_000),
                                 "need_from_recent_nap_milli": 0},
                "respiratory_rate": round(14.8 + rnd.uniform(-0.4, 0.4) + 0.6 * fatigue, 2),
                "sleep_performance_percentage": round(min(100, sleep_ms / need * 100)),
                "sleep_consistency_percentage": rnd.randint(70, 92),
                "sleep_efficiency_percentage": round(sleep_ms / in_bed * 100, 2),
            },
        })
        start = wake + timedelta(hours=1.5)
        for j, (name, mins, strain, avg, mx, km) in enumerate(sess):
            if is_today and j > 0:
                break
            ws = start + timedelta(hours=9 * j)
            total = mins * 60_000
            split = {"Swimming": [0.05, 0.30, 0.42, 0.17, 0.06, 0.0],
                     "Cycling": [0.03, 0.14, 0.33, 0.30, 0.17, 0.03],
                     "Running": [0.02, 0.10, 0.36, 0.32, 0.17, 0.03]}.get(name, [0.1, 0.4, 0.35, 0.12, 0.03, 0.0])
            workouts.append({
                "id": f"10000000-0000-4000-8000-{cid * 10 + j:012d}", "user_id": 1,
                "start": _iso(ws), "end": _iso(ws + timedelta(minutes=mins)), "timezone_offset": TZ,
                "sport_name": name, "score_state": "SCORED",
                "score": {"strain": strain, "average_heart_rate": avg, "max_heart_rate": mx,
                          "kilojoule": round(mins * (11 if name != "Swimming" else 9) * 4.184 * 1.6),
                          "percent_recorded": 100, "distance_meter": km * 1000 if km else None,
                          "altitude_gain_meter": 320 if name == "Cycling" else None, "altitude_change_meter": None,
                          "zone_durations": {k: round(total * s) for k, s in zip(
                              ["zone_zero_milli", "zone_one_milli", "zone_two_milli",
                               "zone_three_milli", "zone_four_milli", "zone_five_milli"], split)}},
            })
    return {"cycles": cycles, "recoveries": recs, "sleeps": sleeps, "workouts": workouts}

from datetime import date, timedelta

from whoop_mcp import analytics as an
from whoop_mcp import demo

TODAY = date(2026, 10, 20)


def _table():
    raw = demo.generate(end=TODAY, days=30)
    return raw, an.daily_table(raw["cycles"], raw["recoveries"], raw["sleeps"], raw["workouts"])


def test_classify_sport():
    assert an.classify_sport("Swimming") == "swim"
    assert an.classify_sport("Cycling") == "bike"
    assert an.classify_sport("Mountain Biking") == "bike"
    assert an.classify_sport("Running") == "run"
    assert an.classify_sport("Triathlon") == "tri"
    assert an.classify_sport("Weightlifting") == "strength"
    assert an.classify_sport("Yoga") == "recovery"
    assert an.classify_sport("meditation") == "recovery"
    assert an.classify_sport("sprint-training") == "run"
    assert an.classify_sport("bodybuilding") == "strength"
    assert an.classify_sport("weightlifting_msk") == "strength"
    assert an.classify_sport("walking") == "other"
    assert an.classify_sport(None) == "other"


def test_target_strain_bands():
    assert an.target_strain(80)["low"] == 14
    assert an.target_strain(50)["high"] == 14
    assert an.target_strain(20)["high"] == 10
    assert an.target_strain(None) is None


def test_stress_estimate():
    assert an.stress_estimate(80, 80, 50, 50)["score"] == 0
    s = an.stress_estimate(64, 80, 55, 50)  # 20% HRV drop (2) + 10% RHR rise (2) -> capped 3
    assert s["score"] == 3 and s["level"] == "high"
    assert an.stress_estimate(None, 80, 50, 50) is None


def test_cycle_day_maps_late_night_start_to_waking_day():
    c = {"start": "2026-10-20T03:30:00.000Z", "timezone_offset": "-05:00"}  # 22:30 local on the 19th
    assert an.cycle_day(c) == date(2026, 10, 20)


def test_daily_table_and_recovery_report():
    _, table = _table()
    rep = an.recovery_report(table, TODAY)
    assert rep["available"]
    assert 0 <= rep["recovery_score"] <= 100
    assert rep["hrv_baseline_7d_ms"] is not None
    assert rep["readiness_zone"] in ("green", "yellow", "red")
    assert rep["target_strain"]["derived"] is True


def test_recovery_missing_day():
    _, table = _table()
    assert an.recovery_report(table, TODAY + timedelta(days=5))["available"] is False


def test_sleep_report_debt():
    raw, table = _table()
    rep = an.sleep_report(table, raw["sleeps"], TODAY)
    s = rep["sleep"]
    assert rep["available"]
    assert s["hours_asleep"] < s["hours_in_bed"]
    stages = s["stages_h"]
    assert abs(sum(stages.values()) - s["hours_in_bed"]) < 0.05
    assert len(rep["sleep_debt"]["nights"]) == 7
    assert rep["sleep_debt"]["rolling_7d_h"] >= 0


def test_sleep_summary_manual():
    s = {
        "id": "x", "start": "2026-10-20T03:00:00Z", "end": "2026-10-20T11:00:00Z", "timezone_offset": "+00:00",
        "nap": False, "score_state": "SCORED",
        "score": {"stage_summary": {"total_in_bed_time_milli": 8 * 3_600_000, "total_awake_time_milli": 3_600_000,
                                    "total_no_data_time_milli": 0, "disturbance_count": 5},
                  "sleep_needed": {"baseline_milli": 7 * 3_600_000, "need_from_sleep_debt_milli": 3_600_000,
                                   "need_from_recent_strain_milli": 0, "need_from_recent_nap_milli": 0},
                  "sleep_performance_percentage": 88},
    }
    out = an.summarize_sleep(s)
    assert out["hours_asleep"] == 7.0
    assert out["hours_needed"] == 8.0
    assert out["awakenings"] == 5


def test_strain_report_and_totals():
    _, table = _table()
    rep = an.strain_report(table, TODAY, 7)
    assert len(rep["days"]) == 7
    assert rep["days"][0]["in_progress"] is True
    assert set(rep["discipline_totals"]) <= {"swim", "bike", "run", "tri", "strength", "other"}
    w = next(w for d in rep["days"] for w in d["workouts"])
    assert w["zone_minutes"] and w["duration_min"] > 0


def test_weekly_trends():
    _, table = _table()
    t = an.weekly_trends(table, TODAY)
    assert len(t["series"]) == 7
    assert t["status"] in ("ok", "watch", "caution")
    assert t["baselines_28d"]["hrv"] is not None
    assert t["acute_chronic_strain_ratio"] is not None


def test_unscored_records_ignored():
    rec = {"score_state": "PENDING_SCORE", "score": {"recovery_score": 99}}
    assert an.scored(rec) == {}


def test_parse_day():
    assert an.parse_day("today", TODAY) == TODAY
    assert an.parse_day("yesterday", TODAY) == TODAY - timedelta(days=1)
    assert an.parse_day("2026-10-01", TODAY) == date(2026, 10, 1)

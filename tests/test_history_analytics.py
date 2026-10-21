from whoop_mcp import history_analytics as ha


def wo(d, disc, minutes=60, zones=None):
    return {"date": d, "discipline": disc, "minutes": minutes, "zones": zones or [0] * 6}


def test_weekly_load_buckets_by_monday_and_skips_non_training():
    days = [{"date": "2026-10-05", "strain": 10.0}, {"date": "2026-10-07", "strain": 6.0},
            {"date": "2026-10-20", "strain": None}]
    workouts = [wo("2026-10-05", "run", 30), wo("2026-10-11", "strength", 90),
                wo("2026-10-12", "swim", 45), wo("2026-10-12", "recovery", 20)]
    res = ha.weekly_load(days, workouts)
    assert [w["week"] for w in res["weeks"]] == ["2026-10-05", "2026-10-12", "2026-10-19"]
    first = res["weeks"][0]
    assert first["hours"]["run"] == 0.5 and first["hours"]["strength"] == 1.5
    assert first["sessions"] == 2 and first["avg_strain"] == 8.0
    assert res["weeks"][1]["sessions"] == 1  # the recovery session does not count
    assert res["weeks"][2] == {"week": "2026-10-19", "hours": {k: 0.0 for k in ha.TRAINING},
                               "sessions": 0, "total_hours": 0.0, "avg_strain": None}


def test_weekly_load_days_since_each_discipline():
    res = ha.weekly_load([{"date": "2026-10-20"}], [wo("2026-10-01", "swim"), wo("2026-09-10", "swim")])
    assert res["as_of"] == "2026-10-20"
    assert res["last_session"]["swim"] == {"date": "2026-10-01", "days": 19}
    assert res["last_session"]["bike"] == {"date": None, "days": None}


def test_weekly_load_empty():
    assert ha.weekly_load([], [])["weeks"] == []

from whoop_mcp import strength_analytics as sa

EX = [
    {"id": 1, "name": "Back Squat", "pattern": "squat", "muscles": ["quads", "glutes"], "push_pull": "none", "region": "lower", "bodyweight": False},
    {"id": 2, "name": "Pull-up", "pattern": "pull", "muscles": ["back", "biceps"], "push_pull": "pull", "region": "upper", "bodyweight": True},
    {"id": 3, "name": "Bench Press", "pattern": "push", "muscles": ["chest", "triceps"], "push_pull": "push", "region": "upper", "bodyweight": False},
]


def st(ex, reps, kg, warmup=False):
    return {"exercise_id": ex, "reps": reps, "weight_kg": kg, "rpe": None, "warmup": warmup}


def sess(i, d, sets):
    return {"id": i, "date": d, "whoop_workout_id": None, "notes": "", "sets": sets}


def test_e1rm_epley_and_limits():
    assert sa.e1rm(100, 1) == 100
    assert sa.e1rm(100, 5) == 116.7
    assert sa.e1rm(100, 13) is None and sa.e1rm(0, 5) is None


def test_progress_prs_bodyweight_and_warmups():
    sessions = [
        sess(1, "2026-09-01", [st(1, 5, 60, warmup=True), st(1, 5, 100), st(1, 5, 100), st(2, 8, 0)]),
        sess(2, "2026-09-08", [st(1, 5, 95)]),
        sess(3, "2026-10-01", [st(1, 3, 115), st(2, 5, 10)]),
    ]
    prog = {p["name"]: p for p in sa.exercise_progress(sessions, EX, body_kg=75)}
    squat = prog["Back Squat"]
    assert [p["pr"] for p in squat["points"]] == [True, False, True]
    first = squat["points"][0]
    assert first["sets"] == 2 and first["volume_kg"] == 1000  # warm-up left out
    assert squat["pr_e1rm"] == 126.5 and squat["pr_date"] == "2026-10-01"
    assert squat["change_4w_pct"] == round(100 * (126.5 / 116.7 - 1), 1)
    # Pull-up load is body weight + added kg
    pull = prog["Pull-up"]["points"]
    assert pull[0]["top_set"] == {"kg": 75, "reps": 8} and pull[1]["e1rm"] == round(85 * (1 + 5 / 30), 1)


def test_weekly_balance_counts_main_and_secondary_muscles():
    sessions = [sess(1, "2026-10-13", [st(1, 5, 100), st(3, 8, 60), st(3, 8, 60)]),
                sess(2, "2026-10-15", [st(2, 6, 0), st(1, 5, 0, warmup=True)])]
    wk = sa.weekly_balance(sessions, EX)["weeks"]
    assert len(wk) == 1 and wk[0]["week"] == "2026-10-12"  # Monday
    w = wk[0]
    assert w["sessions"] == 2 and w["sets"] == 4
    assert w["muscles"] == {"quads": 1, "glutes": 0.5, "chest": 2, "triceps": 1, "back": 1, "biceps": 0.5}
    assert (w["push"], w["pull"]) == (2, 1) and w["region"] == {"lower": 1, "upper": 3}


def test_recovery_link():
    sessions = [sess(1, "2026-09-01", [st(1, 5, 100)]),
                sess(2, "2026-09-03", [st(1, 5, 90)]),   # 90% of the previous best, on a red day
                sess(3, "2026-09-05", [st(1, 5, 105)])]  # 105%, on a green day
    prog = sa.exercise_progress(sessions, EX)
    rec = {"2026-09-01": 70, "2026-09-02": 60, "2026-09-03": 30, "2026-09-05": 80, "2026-09-06": 75}
    link = sa.recovery_link(sessions, prog, rec)
    by = {s["session_id"]: s for s in link["sessions"]}
    assert by[1]["performance_pct"] is None  # no earlier best to compare with
    assert by[2]["performance_pct"] == 90.0 and by[3]["performance_pct"] == 105.0
    assert link["by_zone"]["red"] == {"sessions": 1, "avg_performance_pct": 90.0}
    assert link["by_zone"]["green"]["avg_performance_pct"] == 105.0
    assert link["avg_next_day_change"] == -7.5  # (60-70) and (75-80)

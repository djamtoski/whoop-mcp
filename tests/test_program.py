import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from whoop_mcp import config, program, strength

BODY = {"max_heart_rate": 185, "weight_kilogram": 74.5}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "STRENGTH_DB", tmp_path / "strength.db")
    monkeypatch.setattr(config, "PROGRAM_FILE", tmp_path / "program.json")


def season():
    return program.build(program.DEFAULTS, BODY)


def test_load_maths_matches_rpe_tables():
    assert program.pct_1rm(1, 10) == 1.0
    assert round(program.pct_1rm(5, 8), 3) == 0.811
    assert round(program.pct_1rm(8, 7), 3) == 0.732
    # 100 kg x 5 @ RPE 8 is ~123 kg; without an RPE the same set counts as a max set
    assert program.e1rm(100, 5, 8) == 123.3
    assert program.e1rm(100, 5) == 116.7
    assert program.e1rm(100, 15) is None
    assert program.round_load(81.3, 2.5) == 82.5


def test_season_runs_from_start_to_race_with_phases_in_order():
    p = season()
    assert p["meta"]["totalWeeks"] == 45
    assert [ph["key"] for ph in p["phases"]] == ["base1", "base2", "build", "peak", "taper", "race"]
    assert p["weeks"][0]["startDate"] == "2026-11-02" and p["weeks"][-1]["endDate"] == "2027-09-12"
    race_day = p["weeks"][-1]["days"][-1]["workouts"]
    assert race_day[0]["sport"] == "race"
    # 3:1 cycles: every fourth week of base and build is a recovery week
    assert [w["weekNumber"] for w in p["weeks"] if w["isRecoveryWeek"]][:3] == [4, 8, 12]


def test_durations_add_up_and_weeks_stay_near_their_target():
    for w in season()["weeks"]:
        for d in w["days"]:
            for wo in d["workouts"]:
                if wo["sport"] in ("strength", "rest"):
                    continue
                parts = sum(int(m) for m in re.findall(r"^(\d+) min ·", wo["humanReadable"], re.M))
                assert parts == wo["durationMinutes"], wo["id"]
        if w["phaseKey"] in ("base2", "build", "peak") and not w["isRecoveryWeek"]:
            assert w["summary"]["totalHours"] <= w["targetHours"] * 1.06, w["weekNumber"]


def test_strength_follows_the_athletes_split():
    weeks = season()["weeks"]
    names = lambda wk: [w["name"] for d in wk["days"] for w in d["workouts"] if w["sport"] == "strength"]  # noqa: E731
    assert names(weeks[0]) == ["Full Body A", "Full Body B", "Full Body C"]
    assert names(weeks[30]) == ["Full Body A", "Full Body B"]          # build: two sessions
    assert names(weeks[-1]) == []                                     # race week: none
    a1 = next(w for d in weeks[0]["days"] for w in d["workouts"] if w["name"] == "Full Body A")
    assert "Calibration" in a1["description"]
    lifts = [e["name"] for e in a1["exercises"] if e["kind"] == "main"]
    assert lifts == ["Back Squat", "Incline Dumbbell Press", "Pull-up"]
    a6 = next(w for d in weeks[5]["days"] for w in d["workouts"] if w["name"] == "Full Body A")
    assert any(e["name"] == "Bench Press" for e in a6["exercises"])   # barbell from week 5


def test_loads_come_from_logged_sets_including_bodyweight_lifts():
    strength.save_session("2026-11-02", [
        {"exercise": "Back Squat", "reps": 5, "weight_kg": 100, "rpe": 8},
        {"exercise": "Pull-up", "reps": 6, "weight_kg": 10, "rpe": 8},
    ])
    maxes = program.estimated_maxes(strength.list_sessions(), strength.list_exercises(), 74.5, date(2026, 11, 9))
    assert maxes["Back Squat"]["e1rm"] == 123.3
    p = season()
    ids = {e["name"].lower(): e["id"] for e in strength.list_exercises()}
    week2 = p["weeks"][1]
    program.fill_loads(week2, maxes, ids, 74.5)
    a = next(w for d in week2["days"] for w in d["workouts"] if w["name"] == "Full Body A")
    squat = next(e for e in a["exercises"] if e["name"] == "Back Squat")
    assert squat["sets"] == 4 and squat["reps"] == "8" and squat["rpe"] == 7
    assert squat["load"]["kg"] == 90.0 and squat["exercise_id"] == ids["back squat"]
    pull = next(e for e in a["exercises"] if e["name"] == "Pull-up")
    assert pull["load"]["per"] == "added" and pull["load"]["kg"] >= 0
    rdl = next(w for d in week2["days"] for w in d["workouts"] if w["name"] == "Full Body B")["exercises"][1]
    assert rdl["name"] == "Romanian Deadlift" and rdl["load"] is None   # nothing logged yet


def test_new_library_exercises_reach_an_existing_database():
    names = {e["name"] for e in strength.list_exercises()}
    assert {"Chin-up", "ATG Split Squat", "Copenhagen Plank"} <= names


def test_mark_done_ticks_matching_whoop_workouts_and_logged_lifts():
    p = season()
    workouts = [{"date": "2026-11-02", "discipline": "swim", "duration_min": 38}]
    program.mark_done(p, workouts, {"2026-11-02"}, date(2026, 11, 3))
    mon = p["weeks"][0]["days"][0]["workouts"]
    assert all(w["completed"] for w in mon)
    tue = p["weeks"][0]["days"][1]["workouts"]
    assert not tue[0]["completed"]


@pytest.mark.parametrize("patch, msg", [
    ({"race_date": "2027-13-01"}, "YYYY-MM-DD"),
    ({"race_date": "2026-11-20"}, "8 to 60 weeks"),
    ({"weekly_hours": 30}, "4-15"),
    ({"bike": "tandem"}, "gym or road"),
    ({"css": "fast"}, "m:ss"),
    ({"run_lthr": 90}, "120-200"),
    ({"nope": 1}, "unknown setting"),
])
def test_settings_are_validated(patch, msg):
    assert msg in program.check_settings(patch)


def test_settings_save_and_zones_follow_test_results():
    s = program.save_settings({"start_date": "2026-11-11", "run_lthr": 170, "css": "1:55", "bike": "road"})
    assert s["start_date"] == "2026-11-09"          # snapped to Monday
    z = program.zones(program.load_settings(), 185)
    assert z["run"]["hr"]["lthr"] == 170 and not z["run"]["hr"]["estimated"]
    assert z["run"]["hr"]["zones"][1]["hrHigh"] == 151
    assert z["swim"]["zones"][3]["pace"] == "1:55/100m"


def test_api_returns_the_season_and_validates_settings():
    from whoop_mcp.dashboard import app

    c = TestClient(app, base_url="http://localhost")
    r = c.get("/api/program?demo=1")
    assert r.status_code == 200 and r.json()["program"]["meta"]["totalWeeks"] == 45
    assert c.put("/api/program/settings", json={"bike": "tandem"}).json()["detail"] == "bike must be gym or road"
    assert c.put("/api/program/settings", json={"weekly_hours": 9}).json()["weekly_hours"] == 9.0


def test_half_marathon_block_replaces_weeks_before_the_tuneup():
    s = {**program.DEFAULTS, "tuneup_date": "2026-12-12", "tuneup_name": "Skopje Half"}
    weeks = program.build(s)["weeks"]
    block = [w for w in weeks if w.get("tuneup")]
    assert [w["weekNumber"] for w in block] == [2, 3, 4, 5, 6]
    assert not weeks[0].get("tuneup") and not weeks[6].get("tuneup")
    for w in block:
        sports = [x["sport"] for d in w["days"] for x in d["workouts"]]
        assert "bike" not in sports and sports.count("swim") == (1 if w is block[-1] else 2)
    assert [x["sport"] for d in block[0]["days"] for x in d["workouts"]].count("run") == 5
    race = [x for d in block[-1]["days"] for x in d["workouts"] if x["sport"] == "race"]
    assert len(race) == 1 and block[-1]["days"][5]["date"] == "2026-12-12" and race[0] in block[-1]["days"][5]["workouts"]


def test_tuneup_date_is_validated():
    assert program.check_settings({"tuneup_date": "2026-11-03"})  # inside week 1
    assert program.check_settings({"tuneup_date": "2027-08-30"})  # too close to the race
    assert program.check_settings({"tuneup_date": "2026-12-12"}) is None
    assert program.check_settings({"tuneup_date": ""}) is None

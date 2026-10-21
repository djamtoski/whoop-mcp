import pytest
from fastapi.testclient import TestClient

from whoop_mcp import config, strength


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "STRENGTH_DB", tmp_path / "strength.db")


def squat_id():
    return next(e["id"] for e in strength.list_exercises() if e["name"] == "Back Squat")


def test_library_is_seeded_once():
    first = strength.list_exercises()
    assert len(first) == len(strength.LIBRARY)
    assert strength.list_exercises() == first
    pull = next(e for e in first if e["name"] == "Pull-up")
    assert pull["bodyweight"] and pull["push_pull"] == "pull" and pull["muscles"][0] == "back"


def test_save_list_update_delete_session():
    s = strength.save_session("2026-10-14", [
        {"exercise_id": squat_id(), "reps": 5, "weight_kg": 100},
        {"exercise": "bench press", "reps": 8, "weight_kg": 70, "rpe": 8},  # by name, any case
    ], notes="felt good", whoop_workout_id="dd7b")
    assert [x["exercise"] for x in s["sets"]] == ["Back Squat", "Bench Press"]
    assert s["whoop_workout_id"] == "dd7b" and s["sets"][1]["rpe"] == 8

    updated = strength.save_session("2026-10-15", [{"exercise_id": squat_id(), "reps": 3, "weight_kg": 110}],
                                    session_id=s["id"])
    assert updated["date"] == "2026-10-15" and len(updated["sets"]) == 1
    assert [x["id"] for x in strength.list_sessions(since="2026-10-15")] == [s["id"]]
    assert strength.list_sessions(since="2026-10-16") == []

    assert strength.delete_session(s["id"]) and not strength.delete_session(s["id"])
    assert strength.list_sessions() == []


@pytest.mark.parametrize("bad, msg", [
    ([], "at least one set"),
    ([{"exercise": "Nope", "reps": 5}], "unknown exercise"),
    ([{"exercise": "Deadlift", "reps": 0}], "reps"),
    ([{"exercise": "Deadlift", "reps": 5, "weight_kg": 900}], "weight_kg"),
    ([{"exercise": "Deadlift", "reps": 5, "rpe": 12}], "rpe"),
])
def test_invalid_sets_are_rejected_and_nothing_is_written(bad, msg):
    with pytest.raises(ValueError, match=msg):
        strength.save_session("2026-10-14", bad)
    assert strength.list_sessions() == []


def test_add_custom_exercise():
    ex = strength.add_exercise("  Nordic   Curl ", "hinge", ["hamstrings"])
    assert ex["name"] == "Nordic Curl" and ex["region"] == "lower"
    with pytest.raises(ValueError, match="already exists"):
        strength.add_exercise("nordic curl", "hinge", ["hamstrings"])
    with pytest.raises(ValueError, match="muscles"):
        strength.add_exercise("X", "hinge", ["elbows"])


def test_api_round_trip_and_host_check():
    from whoop_mcp.dashboard import app

    c = TestClient(app, base_url="http://localhost")
    r = c.post("/api/strength/sessions", json={"date": "2026-10-14", "sets": [{"exercise_id": squat_id(), "reps": 5, "weight_kg": 100}]})
    assert r.status_code == 200
    sid = r.json()["id"]
    assert c.get("/api/strength/sessions").json()[0]["id"] == sid
    assert c.post("/api/strength/sessions", json={"date": "2026-10-14", "sets": []}).status_code == 400
    assert c.delete(f"/api/strength/sessions/{sid}").status_code == 200
    assert c.delete(f"/api/strength/sessions/{sid}").status_code == 404
    # Requests addressed to another host name (DNS rebinding) are refused.
    assert TestClient(app, base_url="http://evil.example").get("/api/strength/sessions").status_code == 400


def test_check_functions_return_messages_without_writing():
    assert strength.check_session("2026-13-01", [{"exercise": "Deadlift", "reps": 5}]) == "date must be YYYY-MM-DD"
    assert strength.check_session("2026-10-14", [{"exercise": "Deadlift", "reps": "five"}]).endswith("must be numbers")
    assert strength.check_session("2026-10-14", [{"exercise": "Deadlift", "reps": 5}], session_id=99) == "no session 99"
    assert strength.check_session("2026-10-14", [{"exercise": "Deadlift", "reps": 5}]) is None
    assert "already exists" in strength.check_exercise("deadlift", "hinge", ["hamstrings"])
    assert strength.list_sessions() == []


def test_api_400_detail_is_the_validation_message():
    from whoop_mcp.dashboard import app

    c = TestClient(app, base_url="http://localhost")
    r = c.post("/api/strength/sessions", json={"date": "2026-10-14", "sets": [{"exercise_id": 9999, "reps": 5}]})
    assert r.status_code == 400 and r.json()["detail"] == "set 1: unknown exercise 9999"
    r = c.put("/api/strength/sessions/42", json={"date": "2026-10-14", "sets": [{"exercise_id": squat_id(), "reps": 5}]})
    assert r.status_code == 400 and r.json()["detail"] == "no session 42"

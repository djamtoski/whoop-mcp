import pytest
from fastmcp import Client

from whoop_mcp import config, server, views


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "STRENGTH_DB", tmp_path / "strength.db")
    monkeypatch.setattr(config, "PLAN_FILE", tmp_path / "plan.json")

    async def fake_find(svc, day):
        return {"id": "w1", "date": day, "duration_min": 60} if day == "2026-10-14" else None

    monkeypatch.setattr(views, "find_whoop_strength_workout", fake_find)


async def call(name, args):
    async with Client(server.mcp) as c:
        return (await c.call_tool(name, args, raise_on_error=False)).data


async def test_log_strength_session_links_whoop_and_validates():
    res = await call("log_strength_session", {"date": "2026-10-14", "sets": [
        {"exercise": "back squat", "reps": 5, "weight_kg": 100}, {"exercise": "Pull-up", "reps": 8}]})
    assert res["ok"] and res["linked_whoop_workout"]["id"] == "w1"
    assert res["session"]["whoop_workout_id"] == "w1" and len(res["session"]["sets"]) == 2

    unlinked = await call("log_strength_session", {"date": "2026-10-15", "sets": [{"exercise": "Deadlift", "reps": 3, "weight_kg": 140}]})
    assert unlinked["linked_whoop_workout"] is None

    bad = await call("log_strength_session", {"date": "2026-10-15", "sets": [{"exercise": "Moon Press", "reps": 3}]})
    assert "unknown exercise" in bad["error"]


async def test_update_training_plan_patches_only_given_fields():
    res = await call("update_training_plan", {"race_date": "2027-06-13", "weekly_hours": 9})
    assert res["settings"]["race_date"] == "2027-06-13" and res["settings"]["rest_day"] == 4
    cleared = await call("update_training_plan", {"race_date": ""})
    assert cleared["settings"]["race_date"] is None and cleared["settings"]["weekly_hours"] == 9
    assert "weekly_hours" in (await call("update_training_plan", {"weekly_hours": 60}))["error"]

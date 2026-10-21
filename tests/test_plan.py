from datetime import date

import pytest

from whoop_mcp import config, plan


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PLAN_FILE", tmp_path / "plan.json")


def w(d, disc, hour=18):
    return {"date": d, "discipline": disc, "start": f"{d}T{hour:02d}:00:00Z", "duration_min": 60}


# Mondays and Thursdays in Sept/Oct 2026 are gym days; Wednesdays are runs at 07:00.
HISTORY = ([w(f"2026-09-{d:02d}", "strength") for d in (7, 14, 21, 28)]
           + [w(f"2026-09-{d:02d}", "strength") for d in (10, 17, 24)]
           + [w(f"2026-09-{d:02d}", "strength") for d in (8,)]
           + [w(f"2026-09-{d:02d}", "run", 7) for d in (9, 16, 23, 30)])


def test_habits_and_default_strength_days():
    h = plan.habits(HISTORY)
    assert h["weeks"] == 4
    assert h["by_day"][0]["strength"] == 1.0 and h["by_day"][3]["strength"] == 0.75 and h["by_day"][2]["run"] == 1.0
    assert h["hours"] == {"strength": 18, "run": 7}
    # Mon is first; Tue is too close to Mon, so Thu is the second gym day
    assert plan.default_strength_days(h) == [0, 3]


@pytest.mark.parametrize("weeks_out, phase", [(None, "base"), (20, "base"), (10, "build"), (4, "peak"), (2, "taper"), (0, "race week"), (-1, "post-race")])
def test_phase_for(weeks_out, phase):
    today = date(2026, 10, 21)
    race = None if weeks_out is None else str(date.fromordinal(today.toordinal() + weeks_out * 7 + (3 if weeks_out >= 0 else -3)))
    assert plan.phase_for(race, today)["name"] == phase


def test_build_week_respects_days_hours_and_rest():
    s = {**plan.DEFAULTS, "weekly_hours": 8}
    week = plan.build_week(s, plan.habits(HISTORY), date(2026, 10, 21))
    days = week["days"]
    assert [d["weekday"] for d in days] == plan.DAYS and days[0]["date"] == "2026-10-19"
    assert days[4]["rest"] and not days[4]["sessions"]  # Friday off
    assert {x["kind"] for x in days[5]["sessions"]} >= {"long"} and days[5]["sessions"][0]["sport"] == "bike"
    assert any(x["sport"] == "run" and x["kind"] == "long" for x in days[6]["sessions"])
    assert [i for i, d in enumerate(days) if any(x["sport"] == "strength" for x in d["sessions"])] == [0, 3]
    for i, d in enumerate(days):  # quality sessions never land on a gym day
        if i in (0, 3):
            assert not any(x.get("kind") == "quality" for x in d["sessions"])
    total = sum(week["planned_minutes"].values())
    assert abs(total - 8 * 60) <= 40  # rounding to 5 min and minimum session lengths
    assert week["planned_minutes"]["bike"] > week["planned_minutes"]["run"] > week["planned_minutes"]["swim"]


def test_taper_cuts_volume():
    s = {**plan.DEFAULTS, "race_date": "2026-11-01"}
    week = plan.build_week(s, plan.habits(HISTORY), date(2026, 10, 21))
    assert week["phase"]["name"] == "taper" and sum(week["planned_minutes"].values()) < 0.7 * 8 * 60


def test_adjust_for_recovery():
    q = {"sport": "bike", "kind": "quality"}
    gym = {"sport": "strength", "kind": "full body"}
    assert plan.adjust_for_recovery(q, None) is None
    assert plan.adjust_for_recovery(q, 80)["action"] == "as planned"
    assert plan.adjust_for_recovery(q, 50)["action"] == "cap intensity"
    assert plan.adjust_for_recovery(gym, 50)["action"] == "lighter"
    assert plan.adjust_for_recovery(gym, 20)["action"] == "swap"


def test_mark_done_matches_sport_per_day():
    week = {"days": [{"date": "2026-10-19", "sessions": [{"sport": "strength"}, {"sport": "swim"}]}]}
    plan.mark_done(week, [w("2026-10-19", "strength"), w("2026-10-19", "run")])
    day = week["days"][0]
    assert [s["done"] for s in day["sessions"]] == [True, False]
    assert day["extra"] == [{"sport": "run", "minutes": 60}]


def test_settings_validation_and_persistence():
    assert plan.load_settings() == plan.DEFAULTS
    s = plan.save_settings({"race_date": "2027-06-13", "weekly_hours": 9, "strength_days": [3, 0, 0]})
    assert s["strength_days"] == [0, 3] and plan.load_settings()["race_date"] == "2027-06-13"
    for bad in ({"weekly_hours": 40}, {"race_date": "next june"}, {"rest_day": 5}, {"strength_days": [9]}, {"colour": "red"}):
        with pytest.raises(ValueError):
            plan.save_settings(bad)


def test_no_sport_twice_on_one_day_in_base():
    week = plan.build_week({**plan.DEFAULTS}, plan.habits(HISTORY), date(2026, 10, 21))
    for d in week["days"]:
        sports = [x["sport"] for x in d["sessions"]]
        assert len(sports) == len(set(sports)), d

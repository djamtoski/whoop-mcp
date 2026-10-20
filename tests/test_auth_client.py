import json
import time
from datetime import datetime, timezone

import httpx
import pytest
import respx

from whoop_mcp import auth, config, insights
from whoop_mcp.client import WhoopClient


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TOKEN_FILE", tmp_path / "whoop_tokens.json")
    monkeypatch.setattr(config, "INSIGHTS_FILE", tmp_path / "insights.json")
    monkeypatch.setenv("WHOOP_CLIENT_ID", "cid")
    monkeypatch.setenv("WHOOP_CLIENT_SECRET", "secret")
    return tmp_path


def _write_tokens(expires_in: int, access="old", refresh="r1"):
    auth.save_tokens({"access_token": access, "refresh_token": refresh, "expires_in": expires_in})


def test_save_and_load_tokens():
    _write_tokens(3600)
    tok = auth.load_tokens()
    assert tok["access_token"] == "old"
    assert tok["expires_at"] > time.time() + 3000


@respx.mock
async def test_expired_token_is_refreshed_and_persisted():
    _write_tokens(-10)
    route = respx.post(config.TOKEN_URL).mock(return_value=httpx.Response(
        200, json={"access_token": "new", "refresh_token": "r2", "expires_in": 3600}))
    async with httpx.AsyncClient() as http:
        token = await auth.TokenManager().access_token(http)
    assert token == "new"
    assert route.called
    sent = dict(x.split("=") for x in route.calls[0].request.content.decode().split("&"))
    assert sent["grant_type"] == "refresh_token" and sent["refresh_token"] == "r1"
    assert auth.load_tokens()["refresh_token"] == "r2"


async def test_not_logged_in():
    async with httpx.AsyncClient() as http:
        with pytest.raises(auth.AuthError):
            await auth.TokenManager().access_token(http)


@respx.mock
async def test_client_paginates_and_retries_401():
    _write_tokens(3600)
    respx.post(config.TOKEN_URL).mock(return_value=httpx.Response(
        200, json={"access_token": "fresh", "refresh_token": "r2", "expires_in": 3600}))
    url = f"{config.API_BASE}/v2/recovery"
    calls = {"n": 0}

    def handler(request: httpx.Request):
        calls["n"] += 1
        if request.headers["Authorization"] == "Bearer old":
            return httpx.Response(401)
        if "nextToken" not in request.url.params:
            return httpx.Response(200, json={"records": [{"cycle_id": 1}], "next_token": "p2"})
        return httpx.Response(200, json={"records": [{"cycle_id": 2}]})

    respx.get(url).mock(side_effect=handler)
    client = WhoopClient()
    recs = await client.recoveries(datetime(2026, 10, 1, tzinfo=timezone.utc))
    await client.aclose()
    assert [r["cycle_id"] for r in recs] == [1, 2]
    assert calls["n"] == 3  # 401, page1, page2


def test_authorize_url_contains_scopes_and_state():
    url = auth.build_authorize_url("abc")
    assert "state=abc" in url and "offline" in url and "read%3Arecovery" in url


def test_insights_store_roundtrip():
    insights.add_insight("## Go\nRide threshold.", "Bike day")
    insights.add_insight("Second")
    items = insights.list_insights()
    assert [i["markdown"] for i in items] == ["Second", "## Go\nRide threshold."]
    assert items[1]["title"] == "Bike day"
    with pytest.raises(ValueError):
        insights.add_insight("   ")
    json.loads(config.INSIGHTS_FILE.read_text())


@respx.mock
def test_dashboard_completes_pending_login(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PENDING_LOGIN_FILE", tmp_path / "pending_login.json")
    respx.post(config.TOKEN_URL).mock(return_value=httpx.Response(
        200, json={"access_token": "a", "refresh_token": "r", "expires_in": 3600}))
    auth._write_json(config.PENDING_LOGIN_FILE, {"state": "s1", "created_at": time.time()})

    status, _ = auth.complete_pending_login({"state": ["wrong"], "code": ["c"]})
    assert status == 400
    status, _ = auth.complete_pending_login({"state": ["s1"], "code": ["c"]})
    assert status == 200
    assert json.loads(config.PENDING_LOGIN_FILE.read_text())["result"] == {"ok": True}
    assert auth.load_tokens()["access_token"] == "a"


def test_callback_without_pending_login(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PENDING_LOGIN_FILE", tmp_path / "none.json")
    status, html = auth.complete_pending_login({"state": ["x"], "code": ["c"]})
    assert status == 400 and "No login in progress" in html

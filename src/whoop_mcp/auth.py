"""WHOOP OAuth2: browser login, token persistence and automatic refresh."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from . import config

EXPIRY_SKEW_S = 60


class AuthError(RuntimeError):
    pass


# --------------------------------------------------------------------------- storage

def load_tokens(path: Path | None = None) -> dict[str, Any] | None:
    path = path or config.TOKEN_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_tokens(payload: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Normalise a token-endpoint response and write it atomically."""
    path = path or config.TOKEN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tokens = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "token_type": payload.get("token_type", "bearer"),
        "scope": payload.get("scope"),
        "expires_at": time.time() + int(payload.get("expires_in", 3600)),
    }
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tokens-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return tokens


def _expired(tokens: dict[str, Any]) -> bool:
    return time.time() >= float(tokens.get("expires_at", 0)) - EXPIRY_SKEW_S


# --------------------------------------------------------------------------- refresh

class TokenManager:
    """Hands out a valid access token, refreshing (and persisting) when needed.

    Refresh tokens rotate on use. Because the MCP server and a standalone dashboard
    can run as separate processes, the token file is re-read before refreshing so a
    token another process already refreshed is picked up instead of reusing a stale
    refresh token.
    """

    def __init__(self, path: Path | None = None):
        self.path = path or config.TOKEN_FILE
        self._lock = asyncio.Lock()

    async def access_token(self, http: httpx.AsyncClient, force_refresh: bool = False) -> str:
        async with self._lock:
            tokens = load_tokens(self.path)
            if not tokens:
                raise AuthError("Not logged in to WHOOP. Run: python -m whoop_mcp login")
            if force_refresh or _expired(tokens):
                tokens = await self._refresh(http, tokens)
            return tokens["access_token"]

    async def _refresh(self, http: httpx.AsyncClient, tokens: dict[str, Any]) -> dict[str, Any]:
        if not tokens.get("refresh_token"):
            raise AuthError("No refresh token stored. Run: python -m whoop_mcp login")
        cid, secret = config.client_credentials()
        resp = await http.post(
            config.TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": cid,
                "client_secret": secret,
                "scope": "offline",
            },
        )
        if resp.status_code >= 400:
            # Another process may have rotated the refresh token in the meantime.
            latest = load_tokens(self.path)
            if latest and latest.get("refresh_token") != tokens.get("refresh_token") and not _expired(latest):
                return latest
            raise AuthError(
                f"WHOOP token refresh failed ({resp.status_code}). "
                "Run: python -m whoop_mcp login"
            )
        return save_tokens(resp.json(), self.path)


# --------------------------------------------------------------------------- login CLI

def build_authorize_url(state: str) -> str:
    cid, _ = config.client_credentials()
    return config.AUTH_URL + "?" + urlencode(
        {
            "response_type": "code",
            "client_id": cid,
            "redirect_uri": config.REDIRECT_URI,
            "scope": " ".join(config.SCOPES),
            "state": state,
        }
    )


def exchange_code(code: str) -> dict[str, Any]:
    cid, secret = config.client_credentials()
    resp = httpx.post(
        config.TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.REDIRECT_URI,
            "client_id": cid,
            "client_secret": secret,
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        raise AuthError(f"Code exchange failed ({resp.status_code}): {resp.text[:300]}")
    return save_tokens(resp.json())


_PAGE = """<!doctype html><meta charset="utf-8"><title>WHOOP MCP</title>
<body style="font-family:system-ui;background:#0b0b0f;color:#eee;display:grid;place-items:center;height:100vh;margin:0">
<div style="text-align:center"><h1 style="font-size:28px">{title}</h1><p style="color:#999">{body}</p></div></body>"""


def handle_callback(query: dict[str, list[str]], expected_state: str | None) -> tuple[int, str, str, dict[str, Any]]:
    """Validate an OAuth redirect and exchange the code. Returns (status, title, body, result)."""
    if not expected_state or query.get("state", [None])[0] != expected_state:
        return 400, "State mismatch", "Please restart the login.", {"error": "state mismatch"}
    if "error" in query:
        msg = query.get("error_description", query["error"])[0]
        return 400, "Authorization denied", msg, {"error": query["error"][0]}
    if "code" not in query:
        return 400, "Missing code", "", {"error": "missing code"}
    try:
        exchange_code(query["code"][0])
    except Exception as e:  # noqa: BLE001
        return 500, "Token exchange failed", str(e), {"error": str(e)}
    return 200, "WHOOP connected &#10003;", "Tokens saved. You can close this tab.", {"ok": True}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def complete_pending_login(query: dict[str, list[str]]) -> tuple[int, str]:
    """Called by the dashboard's /callback when it (not the CLI) owns the redirect port."""
    try:
        pending = json.loads(config.PENDING_LOGIN_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return 400, _PAGE.format(title="No login in progress",
                                 body="Run <code>python -m whoop_mcp login</code> first.")
    if time.time() - pending.get("created_at", 0) > 600:
        return 400, _PAGE.format(title="Login expired", body="Re-run <code>python -m whoop_mcp login</code>.")
    status, title, body, result = handle_callback(query, pending.get("state"))
    _write_json(config.PENDING_LOGIN_FILE, {**pending, "result": result})
    return status, _PAGE.format(title=title, body=body)


def _login_via_running_dashboard(state: str, timeout_s: int, open_browser: bool) -> Path:
    """Port is held by our own dashboard: hand the state to it and wait for the result."""
    _write_json(config.PENDING_LOGIN_FILE, {"state": state, "created_at": time.time()})
    try:
        url = build_authorize_url(state)
        print("Callback port is in use by the running dashboard; it will complete the login.")
        print(f"Opening browser for WHOOP consent...\nIf it doesn't open, visit:\n\n  {url}\n")
        if open_browser:
            webbrowser.open(url)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                result = json.loads(config.PENDING_LOGIN_FILE.read_text(encoding="utf-8")).get("result")
            except (FileNotFoundError, json.JSONDecodeError):
                result = None
            if result:
                if result.get("ok"):
                    return config.TOKEN_FILE
                raise AuthError(f"Login failed: {result.get('error')}")
            time.sleep(1)
        raise AuthError("Timed out waiting for the WHOOP callback. Is the dashboard running the latest code?")
    finally:
        config.PENDING_LOGIN_FILE.unlink(missing_ok=True)


def login(timeout_s: int = 300, open_browser: bool = True) -> Path:
    """Run the one-off OAuth consent flow.

    Uses a temporary local callback server, or - if the dashboard already owns the redirect
    port (e.g. Claude Code is running the MCP server) - lets the dashboard's /callback finish it.
    """
    state = secrets.token_urlsafe(24)
    redirect = urlparse(config.REDIRECT_URI)
    result: dict[str, Any] = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default logging
            pass

        def do_GET(self):
            url = urlparse(self.path)
            if url.path != redirect.path:
                status, html = 404, _PAGE.format(title="Not found", body="")
            else:
                status, title, body, res = handle_callback(parse_qs(url.query), state)
                result.update(res)
                html = _PAGE.format(title=title, body=body)
                done.set()
            data = html.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    host = redirect.hostname or "localhost"
    port = redirect.port or 80
    try:
        server = HTTPServer((host if host != "localhost" else "127.0.0.1", port), Handler)
    except OSError:
        return _login_via_running_dashboard(state, timeout_s, open_browser)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = build_authorize_url(state)
    print(f"Opening browser for WHOOP consent...\nIf it doesn't open, visit:\n\n  {url}\n")
    if open_browser:
        webbrowser.open(url)
    try:
        if not done.wait(timeout_s):
            raise AuthError("Timed out waiting for the WHOOP callback.")
    finally:
        server.shutdown()
        server.server_close()
    if not result.get("ok"):
        raise AuthError(f"Login failed: {result.get('error')}")
    return config.TOKEN_FILE

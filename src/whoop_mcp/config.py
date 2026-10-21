"""Paths, environment and WHOOP API constants."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

API_BASE = "https://api.prod.whoop.com/developer"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
SCOPES = [
    "offline",  # required to receive a refresh_token
    "read:recovery",
    "read:cycles",
    "read:sleep",
    "read:workout",
    "read:profile",
    "read:body_measurement",
]

DATA_DIR = Path(os.environ.get("WHOOP_MCP_HOME", Path.home() / ".whoop-mcp"))
TOKEN_FILE = DATA_DIR / "whoop_tokens.json"
INSIGHTS_FILE = DATA_DIR / "insights.json"
STRENGTH_DB = DATA_DIR / "strength.db"
PLAN_FILE = DATA_DIR / "plan.json"
PENDING_LOGIN_FILE = DATA_DIR / "pending_login.json"

HOST = os.environ.get("WHOOP_DASHBOARD_HOST", "127.0.0.1")
PORT = int(os.environ.get("WHOOP_DASHBOARD_PORT", "8000"))
REDIRECT_URI = os.environ.get("WHOOP_REDIRECT_URI", f"http://localhost:{PORT}/callback")

STATIC_DIR = Path(__file__).resolve().parent / "static"


def client_credentials() -> tuple[str, str]:
    # Re-read .env so a long-running server picks up credentials added after it started.
    load_dotenv(PROJECT_ROOT / ".env")
    cid = os.environ.get("WHOOP_CLIENT_ID", "").strip()
    secret = os.environ.get("WHOOP_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        raise RuntimeError(
            "WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must be set "
            "(environment variables or a .env file in the project root)."
        )
    return cid, secret

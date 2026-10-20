"""File-backed store for Claude's coaching insights (shared by MCP + dashboard processes)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

MAX_INSIGHTS = 50
MAX_CHARS = 20_000
_lock = threading.Lock()


def _path() -> Path:
    return config.INSIGHTS_FILE


def list_insights() -> list[dict[str, Any]]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def add_insight(markdown_text: str, title: str | None = None) -> dict[str, Any]:
    text = (markdown_text or "").strip()
    if not text:
        raise ValueError("markdown_text is empty")
    item = {
        "id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": (title or "").strip()[:120] or None,
        "markdown": text[:MAX_CHARS],
    }
    with _lock:
        items = [item, *list_insights()][:MAX_INSIGHTS]
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".insights-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
        os.replace(tmp, path)
    return item


def version() -> float:
    """Changes whenever the store is written; used by the dashboard SSE loop."""
    try:
        return _path().stat().st_mtime_ns
    except FileNotFoundError:
        return 0

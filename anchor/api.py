"""The JSON API as a plain function, with no server attached.

web.py serves it over HTTP. The browser demo calls it directly inside
Pyodide. Both go through the same core Store, so there is one code path.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from .core import CoreError, Store

# POST /api/<action> maps straight onto a core function. No other write path.
ACTIONS = ("propose", "validate", "check_conflict", "confirm_conflict", "checkout", "release")


def handle(store: Store, method: str, path: str, body: Any = None) -> tuple[int, Any]:
    """Route one API request. Returns (http_status, json_ready_data)."""
    url = urlparse(path)
    parts = [p for p in url.path.split("/") if p]
    try:
        if method == "GET":
            q = {k: v[0] for k, v in parse_qs(url.query).items() if v and v[0]}
            if parts == ["api", "findings"]:
                return 200, store.query(q.get("q", ""), tier=q.get("tier"), status=q.get("status"), limit=500)
            if parts == ["api", "config"]:
                return 200, store.team_config()
            if parts == ["api", "activity"]:
                return 200, store.activity(int(q.get("limit", 50)))
            if len(parts) == 3 and parts[:2] == ["api", "findings"]:
                return 200, store.get(int(parts[2]))
            if len(parts) == 4 and parts[:2] == ["api", "findings"] and parts[3] == "history":
                return 200, store.history(int(parts[2]))
        elif method == "POST" and len(parts) == 2 and parts[0] == "api" and parts[1] in ACTIONS:
            if not isinstance(body, dict):
                return 400, {"error": "body must be a JSON object"}
            return 200, getattr(store, parts[1])(**body)
    except CoreError as e:
        return 400, {"error": str(e)}
    except (TypeError, ValueError) as e:
        return 400, {"error": f"bad request: {e}"}
    return 404, {"error": "not found"}


def handle_json(store: Store, method: str, path: str, body_text: str = "") -> str:
    """Same as handle, but JSON text in and out. Used by the browser demo."""
    try:
        body = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError:
        return json.dumps({"status": 400, "data": {"error": "body must be JSON"}})
    status, data = handle(store, method, path, body)
    return json.dumps({"status": status, "data": data})

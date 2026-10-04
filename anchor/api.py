"""The JSON API as a plain function, with no server attached.

web.py serves it over HTTP. The browser demo calls it directly inside
Pyodide. Both go through the same core Store, so there is one code path.
"""

from __future__ import annotations

import inspect
import json
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .core import CoreError, Store

# POST /api/<action> maps straight onto a core function. No other write path.
ACTIONS = (
    "whoami", "set_person",
    "start_study", "update_study", "ask_for_research",
    "add", "confirm", "promote", "revise", "review", "ask_for_review", "withdraw_request",
    "link", "check_conflict", "working_on", "follow", "mark_seen",
    "log_decision", "update_decision",
    "add_source", "update_source", "delete_source", "set_spot", "add_blocks", "break_down", "check",
    "set_package", "retire", "bring_back", "delete", "resolve_conflict",
    "add_question", "update_question", "remove_question", "set_answers",
)

# GET /api/<route> maps onto a core read. {x} is a path value passed first;
# query string values are passed by name when the function takes them.
READS = (
    ("learnings", "query"),
    ("learnings/{id}", "get"),
    ("learnings/{id}/history", "history"),
    ("studies", "list_studies"),
    ("studies/{id}", "get_study"),
    ("workspaces/{id}", "get_workspace"),
    ("questions/{id}/known", "already_known"),
    ("needs-check", "needs_check"),
    ("decisions", "list_decisions"),
    ("decisions/{id}", "get_decision"),
    ("people", "people"),
    ("people/{name}", "person"),
    ("queue", "my_queue"),
    ("next", "next_step"),
    ("digest", "digest"),
    ("activity", "activity"),
    ("config", "team_config"),
)

# Query string names that differ from the core argument name.
ALIASES = {"q": "topic"}


def _match(route: str, parts: list[str]) -> list[Any] | None:
    pattern = route.split("/")
    if len(pattern) != len(parts):
        return None
    values = []
    for want, got in zip(pattern, parts):
        if want == "{id}":
            values.append(int(got))
        elif want.startswith("{"):
            values.append(unquote(got))
        elif want != got:
            return None
    return values


def _read(store: Store, parts: list[str], query: dict[str, str]) -> tuple[int, Any]:
    for route, method in READS:
        values = _match(route, parts)
        if values is None:
            continue
        fn = getattr(store, method)
        params = inspect.signature(fn).parameters
        kwargs = {}
        for key, value in query.items():
            name = ALIASES.get(key, key)
            if name in params:
                kwargs[name] = int(value) if params[name].annotation.startswith("int") else value
        return 200, fn(*values, **kwargs)
    return 404, {"error": "not found"}


def handle(store: Store, method: str, path: str, body: Any = None) -> tuple[int, Any]:
    """Route one API request. Returns (http_status, json_ready_data)."""
    url = urlparse(path)
    parts = [p for p in url.path.split("/") if p]
    try:
        if method == "GET" and parts[:1] == ["api"]:
            query = {k: v[0] for k, v in parse_qs(url.query).items() if v and v[0]}
            return _read(store, parts[1:], query)
        if method == "POST" and len(parts) == 2 and parts[0] == "api" and parts[1] in ACTIONS:
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

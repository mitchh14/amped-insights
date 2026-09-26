"""Web app: a small JSON API plus a single static page.

Every read and write goes through the same core Store the MCP server uses.
Run with:  python -m anchor.web [--port 8000]
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core import DEFAULT_DB_PATH, CoreError, Store

STATIC = Path(__file__).parent / "static"


def make_handler(store: Store):
    # POST /api/<action> maps straight onto a core function. No other write path.
    actions = {
        "propose": store.propose,
        "validate": store.validate,
        "check_conflict": store.check_conflict,
        "confirm_conflict": store.confirm_conflict,
        "checkout": store.checkout,
        "release": store.release,
    }

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def _run(self, fn, *args, **kwargs) -> None:
            try:
                self._json(200, fn(*args, **kwargs))
            except CoreError as e:
                self._json(400, {"error": str(e)})
            except (TypeError, ValueError) as e:
                self._json(400, {"error": f"bad request: {e}"})

        def do_GET(self) -> None:
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items() if v and v[0]}
            parts = [p for p in url.path.split("/") if p]
            if not parts:
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if parts == ["api", "findings"]:
                return self._run(
                    lambda: store.query(q.get("q", ""), tier=q.get("tier"), status=q.get("status"), limit=500)
                )
            if parts == ["api", "activity"]:
                return self._run(store.activity, int(q.get("limit", 50)))
            if len(parts) == 3 and parts[:2] == ["api", "findings"]:
                return self._run(store.get, int(parts[2]))
            if len(parts) == 4 and parts[:2] == ["api", "findings"] and parts[3] == "history":
                return self._run(store.history, int(parts[2]))
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            parts = [p for p in urlparse(self.path).path.split("/") if p]
            if len(parts) != 2 or parts[0] != "api" or parts[1] not in actions:
                return self._json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._json(400, {"error": "body must be JSON"})
            self._run(actions[parts[1]], **body)

        def log_message(self, fmt, *args) -> None:  # keep the console quiet
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="ANCHOR web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    store = Store(args.db)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store))
    print(f"ANCHOR on http://{args.host}:{args.port}  (db: {args.db})")
    server.serve_forever()


if __name__ == "__main__":
    main()

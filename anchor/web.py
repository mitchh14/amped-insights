"""Web app: a small JSON API plus a single static page.

Every read and write goes through the same core Store the MCP server uses.
Routing lives in api.py so the browser demo can share it.
Run with:  python -m anchor.web [--port 8000]
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .api import handle
from .core import DEFAULT_DB_PATH, Store

STATIC = Path(__file__).parent / "static"


def make_handler(store: Store):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def do_GET(self) -> None:
            if urlparse(self.path).path in ("", "/"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            self._json(*handle(store, "GET", self.path))

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._json(400, {"error": "body must be JSON"})
            self._json(*handle(store, "POST", self.path, body))

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

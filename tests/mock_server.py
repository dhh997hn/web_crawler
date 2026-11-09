from __future__ import annotations

import json
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATE = {"logins": 0, "expiring_logins": 0}
VALID_TOKEN = "TOKEN_OK"
ITEMS_PER_PAGE = 3
TOTAL_PAGES = 5


def make_items(page: int) -> list:
    if page > TOTAL_PAGES:
        return []
    return [
        {"id": (page - 1) * ITEMS_PER_PAGE + i + 1, "name": f"item-{page}-{i}", "meta": {"src": page}}
        for i in range(ITEMS_PER_PAGE)
    ]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/auth/login":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        if data.get("username") != "user" or data.get("password") not in ("pass123", "expiring"):
            return self._send(401, {"error": "bad credentials"})
        STATE["logins"] += 1
        if data.get("password") == "expiring":
            STATE["expiring_logins"] += 1
            if STATE["expiring_logins"] == 1:
                return self._send(200, {"data": {"token": "TOKEN_OLD"}})
        return self._send(200, {"data": {"token": VALID_TOKEN}})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/items":
            return self._send(404, {"error": "not found"})
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {VALID_TOKEN}":
            return self._send(401, {"error": "invalid token"})
        qs = parse_qs(parsed.query)
        page = int(qs.get("page", ["1"])[0])
        return self._send(200, {"data": {"items": make_items(page), "totalPages": TOTAL_PAGES, "page": page}})


def serve(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    serve()
    print("mock server on http://127.0.0.1:8765")
    signal.pause()

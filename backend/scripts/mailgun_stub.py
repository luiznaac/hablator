"""Local Mailgun stub for acceptance runs — never imported by the app.

Answers the v3 send endpoint with `200 {"message": "Queued. Thank you."}`, except that the **first**
POST for a `to` field containing `fail` answers `500 {"message": "provider failed"}`. A delivery to
such an address therefore fails once and succeeds when retried, so acceptance can exercise the
retry endpoint without reaching a real provider. Any `GET` answers `200 {"status": "ok"}` for the
readiness gate.

Usage: `uv run python scripts/mailgun_stub.py [port]` (default 8199).
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from urllib.parse import parse_qs

DEFAULT_PORT = 8199


class _Handler(BaseHTTPRequestHandler):
    failed_once: ClassVar[set[str]] = set()

    def do_GET(self) -> None:
        self._respond(200, {"status": "ok"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        recipient = fields.get("to", [""])[0]
        if "fail" in recipient and recipient not in self.failed_once:
            self.failed_once.add(recipient)
            self._respond(500, {"message": "provider failed"})
        else:
            self._respond(200, {"message": "Queued. Thank you."})

    def log_message(self, fmt: str, *args: object) -> None:
        pass

    def _respond(self, status: int, payload: dict[str, str]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    ThreadingHTTPServer(("127.0.0.1", port), _Handler).serve_forever()


if __name__ == "__main__":
    main()

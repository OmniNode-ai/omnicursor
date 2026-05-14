"""HTTP GET /status for the sidecar (stdlib ThreadingHTTPServer).

Returns JSON:
  publisher_mode      — kafka | omnidash | noop (CLI --publisher)
  outbox_offset       — byte offset into outbox.jsonl (same file as drainer cursor)
  events_published    — successful publish() calls since process start

Binds loopback only (127.0.0.1). The daemon passes ``--status-port``; use ``0`` there
to disable the server entirely without calling this module.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from omnicursor.drainer.cursor import read_offset
from omnicursor.drainer.publisher import PublishCounter

_log = logging.getLogger(__name__)


class _StatusHandler(BaseHTTPRequestHandler):
    """Handle GET /status only."""

    server_version = "OmniCursorSidecar/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/status":
            self.send_error(404, "Not Found")
            return

        server = self.server
        assert isinstance(server, StatusHTTPServer)
        offset = read_offset(server.cursor_path)
        published = server.publish_counter.value()
        body_obj = {
            "publisher_mode": server.publisher_mode,
            "outbox_offset": offset,
            "events_published": published,
        }
        data = json.dumps(body_obj, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        _log.debug("status_http %s - %s", self.address_string(), fmt % args)


class StatusHTTPServer(ThreadingHTTPServer):
    """Threading HTTPServer with cursor + metrics on the server object."""

    allow_reuse_address = True

    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        *,
        cursor_path: Path,
        publisher_mode: str,
        publish_counter: PublishCounter,
    ) -> None:
        self.cursor_path = cursor_path
        self.publisher_mode = publisher_mode
        self.publish_counter = publish_counter
        super().__init__(server_address, RequestHandlerClass)


def start_status_server(
    *,
    host: str = "127.0.0.1",
    port: int,
    publisher_mode: str,
    cursor_path: Path,
    publish_counter: PublishCounter,
    logger: logging.Logger | None = None,
) -> tuple[StatusHTTPServer, threading.Thread]:
    """Start HTTP server in a daemon thread.

    Use port 0 to bind an ephemeral port (tests). Callers that want no HTTP server
    must not call this function (the daemon gates on ``--status-port``).
    """
    log = logger or _log

    server = StatusHTTPServer(
        (host, port),
        _StatusHandler,
        cursor_path=cursor_path,
        publisher_mode=publisher_mode,
        publish_counter=publish_counter,
    )
    _, bound_port = server.server_address
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name="omnicursor-status-http",
    )
    thread.start()
    log.info("status_server: GET http://%s:%s/status", host, bound_port)
    return server, thread

"""Unix-socket client for ONEX-style hook events (stdlib only).

Mirrors the wire shape planned for omniclaude's emit daemon: one JSON object
per line (newline-terminated UTF-8). If the socket is missing or send fails,
callers should treat it as a soft failure — hooks must never crash Cursor.

Environment:
  OMNICURSOR_EMIT_SOCKET  — path to Unix socket (default: ~/.omnicursor/emit.sock)
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any, Dict


def default_socket_path() -> Path:
    env = os.environ.get("OMNICURSOR_EMIT_SOCKET")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".omnicursor" / "emit.sock"


def send_event(
    event_type: str,
    payload: Dict[str, Any],
    *,
    timeout_s: float = 0.5,
) -> bool:
    """Send a single event to the emit daemon. Returns True if bytes were sent."""
    sock_path = default_socket_path()
    if not sock_path.exists():
        return False
    try:
        envelope = {"type": event_type, "payload": payload}
        line = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False) + "\n"
        data = line.encode("utf-8")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_s)
            sock.connect(str(sock_path))
            sock.sendall(data)
        return True
    except OSError:
        return False

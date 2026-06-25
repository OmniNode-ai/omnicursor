"""Unix-socket client for ONEX-style hook events (stdlib only).

Compatible with the OmniClaude emit daemon wire protocol:

    Request:  {"event_type": "...", "payload": {...}}\\n
    Response: {"status": "queued", "event_id": "..."}\\n
    Ping:     {"command": "ping"}\\n
    Pong:     {"status": "ok", ...}\\n

The daemon that owns this socket is the shared platform emit daemon
(omnimarket ``node_emit_daemon`` — the same one OmniClaude uses), an
out-of-process service; the hook itself stays stdlib-only and never talks to
Kafka. If the socket is missing or any step fails, ``send_event`` /
``daemon_available`` return False — hooks must never crash Cursor.

Environment:
  OMNICURSOR_EMIT_SOCKET    path to Unix socket (default: ~/.omnicursor/emit.sock)
  OMNICURSOR_EMIT_TIMEOUT   socket timeout in seconds (default: 0.5)
"""

from __future__ import annotations

import json
import math
import os
import socket
from pathlib import Path
from typing import Any, Dict, Optional

_DEFAULT_TIMEOUT_S = 0.5
_MAX_RESPONSE_BYTES = 1_048_576  # 1 MB safety cap on daemon responses


def default_socket_path() -> Path:
    env = os.environ.get("OMNICURSOR_EMIT_SOCKET")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".omnicursor" / "emit.sock"


def _default_timeout_s() -> float:
    env = os.environ.get("OMNICURSOR_EMIT_TIMEOUT")
    if not env:
        return _DEFAULT_TIMEOUT_S
    try:
        value = float(env)
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT_S
    if not math.isfinite(value) or value <= 0:
        return _DEFAULT_TIMEOUT_S
    return value


def _request(message: Dict[str, Any], *, timeout_s: float) -> Optional[Dict[str, Any]]:
    """Send one newline-terminated JSON request and parse the daemon reply.

    Returns the parsed response dict on success, or ``None`` on any failure
    (socket missing, connect refused, broken pipe, timeout, oversize body,
    empty reply, invalid JSON, non-object reply, serialization failure).

    Never raises.
    """
    sock_path = default_socket_path()
    if not sock_path.exists():
        return None

    try:
        data = (
            json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None

    chunks: list[bytes] = []
    total = 0
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_s)
            sock.connect(str(sock_path))
            sock.sendall(data)
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_RESPONSE_BYTES:
                    return None
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
    except OSError:
        # Covers ConnectionRefusedError, BrokenPipeError, FileNotFoundError,
        # socket.timeout (subclass of OSError in 3.10+), and any other socket
        # I/O failure. Treat all as a soft drop.
        return None

    raw = b"".join(chunks).split(b"\n", 1)[0].decode("utf-8", errors="replace").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def send_event(
    event_type: str,
    payload: Dict[str, Any],
    *,
    timeout_s: Optional[float] = None,
) -> bool:
    """Send a single event to the emit daemon.

    Returns True only when the daemon ACKs ``{"status": "queued", ...}``.
    Returns False on every other path (socket missing, timeout, broken pipe,
    connection refused, invalid/empty JSON reply, daemon error status).
    Never raises.
    """
    t = timeout_s if timeout_s is not None else _default_timeout_s()
    response = _request({"event_type": event_type, "payload": payload}, timeout_s=t)
    if response is None:
        return False
    return response.get("status") == "queued"


def daemon_available(*, timeout_s: Optional[float] = None) -> bool:
    """Ping the emit daemon.

    Returns True only when the daemon answers ``{"status": "ok", ...}``.
    Any other reply, missing socket, or transport error returns False.
    Never raises.
    """
    t = timeout_s if timeout_s is not None else _default_timeout_s()
    response = _request({"command": "ping"}, timeout_s=t)
    if response is None:
        return False
    return response.get("status") == "ok"

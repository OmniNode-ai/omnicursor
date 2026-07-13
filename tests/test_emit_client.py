"""Tests for the OmniCursor emit_client (stdlib Unix-socket client).

Exercises the real send/recv path against a tiny in-process Unix-socket
fake daemon. No live infrastructure required.
"""

from __future__ import annotations

import importlib.util as ilu
import json
import shutil
import socket
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / ".cursor" / "hooks" / "lib"


def _load_emit_client():
    name = "emit_client_test_mod"
    spec = ilu.spec_from_file_location(name, _LIB / "emit_client.py")
    mod = ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture
def emit_mod():
    return _load_emit_client()


@pytest.fixture
def short_tmp() -> Path:
    """A short-path tmp dir.

    macOS caps AF_UNIX socket paths at ~104 characters, which pytest's
    default ``tmp_path`` regularly exceeds. Mint a short dir under /tmp
    instead so the fake daemon can bind() successfully.
    """
    d = Path(tempfile.mkdtemp(prefix="oc-emit-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Fake daemon harness
# ---------------------------------------------------------------------------


class _FakeDaemon:
    """Single-connection Unix-socket server used to drive the client.

    Behavior is configured via ``response`` / ``hang`` / ``close_silent``:

    - ``response`` is a bytes payload to send back after reading the request.
    - ``hang`` keeps the connection open without responding (used to drive
      the client's recv timeout).
    - ``close_silent`` closes the connection after reading the request
      without sending any bytes (simulates an empty/aborted reply).
    """

    def __init__(
        self,
        sock_path: Path,
        *,
        response: Optional[bytes] = None,
        hang: bool = False,
        close_silent: bool = False,
    ) -> None:
        self.sock_path = sock_path
        self.response = response
        self.hang = hang
        self.close_silent = close_silent
        self.received: list[bytes] = []
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def __enter__(self) -> "_FakeDaemon":
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.settimeout(2.0)
        self._server.bind(str(self.sock_path))
        self._server.listen(1)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        try:
            if self._server is not None:
                self._server.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        try:
            self.sock_path.unlink()
        except FileNotFoundError:
            pass

    def _run(self) -> None:
        assert self._server is not None
        try:
            conn, _ = self._server.accept()
        except OSError:
            return
        try:
            buf = b""
            while b"\n" not in buf:
                try:
                    chunk = conn.recv(4096)
                except OSError:
                    return
                if not chunk:
                    break
                buf += chunk
            if buf:
                self.received.append(buf)
            if self.hang:
                self._stop.wait(timeout=5.0)
                return
            if self.close_silent:
                return
            if self.response is not None:
                try:
                    conn.sendall(self.response)
                except OSError:
                    return
        finally:
            try:
                conn.close()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# send_event
# ---------------------------------------------------------------------------


def test_send_event_returns_true_when_daemon_acks_queued(
    emit_mod, monkeypatch, short_tmp
) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(
        sock_path, response=b'{"status":"queued","event_id":"evt-1"}\n'
    ) as daemon:
        assert emit_mod.send_event("session.ended", {"k": "v"}) is True
    assert daemon.received, "fake daemon received no bytes"


def test_send_event_returns_false_on_error_ack(
    emit_mod, monkeypatch, short_tmp
) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(sock_path, response=b'{"status":"error","reason":"nope"}\n'):
        assert emit_mod.send_event("session.ended", {}) is False


def test_send_event_returns_false_when_socket_missing(
    emit_mod, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: tmp_path / "nope.sock")
    assert emit_mod.send_event("session.ended", {"a": 1}) is False


def test_send_event_returns_false_on_timeout(emit_mod, monkeypatch, short_tmp) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(sock_path, hang=True):
        assert emit_mod.send_event("session.ended", {}, timeout_s=0.1) is False


def test_send_event_returns_false_when_daemon_closes_silent(
    emit_mod, monkeypatch, short_tmp
) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(sock_path, close_silent=True):
        assert emit_mod.send_event("session.ended", {}) is False


def test_send_event_handles_non_ascii_payload(emit_mod, monkeypatch, short_tmp) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(
        sock_path, response=b'{"status":"queued","event_id":"e1"}\n'
    ) as daemon:
        payload = {"text": "café — emoji 🌮", "list": ["niño", "über"]}
        assert emit_mod.send_event("prompt.submitted", payload) is True
    decoded = daemon.received[0].decode("utf-8")
    assert "café" in decoded
    assert "🌮" in decoded
    assert "niño" in decoded


def test_envelope_uses_event_type_key_not_type(
    emit_mod, monkeypatch, short_tmp
) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(
        sock_path, response=b'{"status":"queued","event_id":"e1"}\n'
    ) as daemon:
        emit_mod.send_event("session.ended", {"k": "v"})
    sent = json.loads(daemon.received[0].split(b"\n", 1)[0].decode("utf-8"))
    assert sent.get("event_type") == "session.ended"
    assert "type" not in sent
    assert sent.get("payload") == {"k": "v"}


def test_send_event_returns_false_on_invalid_json_reply(
    emit_mod, monkeypatch, short_tmp
) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(sock_path, response=b"not-json-at-all\n"):
        assert emit_mod.send_event("session.ended", {}) is False


# ---------------------------------------------------------------------------
# daemon_available
# ---------------------------------------------------------------------------


def test_daemon_available_true_on_ping_ok(emit_mod, monkeypatch, short_tmp) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(sock_path, response=b'{"status":"ok","queue_size":0}\n') as daemon:
        assert emit_mod.daemon_available() is True
    sent = json.loads(daemon.received[0].split(b"\n", 1)[0].decode("utf-8"))
    assert sent.get("command") == "ping"


def test_daemon_available_false_on_error_response(
    emit_mod, monkeypatch, short_tmp
) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(sock_path, response=b'{"status":"error"}\n'):
        assert emit_mod.daemon_available() is False


def test_daemon_available_false_when_socket_missing(
    emit_mod, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: tmp_path / "no.sock")
    assert emit_mod.daemon_available() is False


def test_daemon_available_false_on_timeout(emit_mod, monkeypatch, short_tmp) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    with _FakeDaemon(sock_path, hang=True):
        assert emit_mod.daemon_available(timeout_s=0.1) is False


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------


def test_socket_path_respects_env_override(emit_mod, monkeypatch, tmp_path) -> None:
    custom = tmp_path / "custom.sock"
    monkeypatch.setenv("OMNICURSOR_EMIT_SOCKET", str(custom))
    assert emit_mod.default_socket_path() == custom


def test_timeout_respects_env_override(emit_mod, monkeypatch) -> None:
    monkeypatch.setenv("OMNICURSOR_EMIT_TIMEOUT", "1.25")
    assert emit_mod._default_timeout_s() == 1.25


def test_timeout_falls_back_to_default_on_garbage_env(emit_mod, monkeypatch) -> None:
    monkeypatch.setenv("OMNICURSOR_EMIT_TIMEOUT", "not-a-float")
    assert emit_mod._default_timeout_s() == 0.5


def test_timeout_falls_back_to_default_on_negative_env(emit_mod, monkeypatch) -> None:
    monkeypatch.setenv("OMNICURSOR_EMIT_TIMEOUT", "-1")
    assert emit_mod._default_timeout_s() == 0.5


def test_timeout_falls_back_to_default_on_zero_env(emit_mod, monkeypatch) -> None:
    monkeypatch.setenv("OMNICURSOR_EMIT_TIMEOUT", "0")
    assert emit_mod._default_timeout_s() == 0.5


def test_timeout_falls_back_to_default_on_nan_env(emit_mod, monkeypatch) -> None:
    monkeypatch.setenv("OMNICURSOR_EMIT_TIMEOUT", "nan")
    assert emit_mod._default_timeout_s() == 0.5


def test_send_event_does_not_raise_on_bad_timeout_env(
    emit_mod, monkeypatch, short_tmp
) -> None:
    sock_path = short_tmp / "emit.sock"
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: sock_path)
    monkeypatch.setenv("OMNICURSOR_EMIT_TIMEOUT", "-1")
    with _FakeDaemon(sock_path, response=b'{"status":"queued","event_id":"e1"}\n'):
        # Bad env must not propagate as ValueError from sock.settimeout(...).
        result = emit_mod.send_event("session.ended", {"k": "v"})
    assert result is True

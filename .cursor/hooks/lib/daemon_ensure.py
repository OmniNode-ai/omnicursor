"""Best-effort provisioning of the shared emit daemon (stdlib only).

Gives the pinned Unix socket a live owner: the **shared platform emit daemon**
(omnimarket ``node_emit_daemon`` — the same one OmniClaude uses), spawned
detached with the fork's event registry, the pinned socket path, and a real
Kafka broker. There is no Cursor-specific transport variant; this module only
provisions the shared path on a Cursor-owned socket.

Contract:
  - Fast liveness ping first; when a daemon already owns the socket, return
    immediately (the common path).
  - Otherwise spawn the daemon DETACHED via ``/bin/sh -c`` and return without
    waiting. The wrapper first verifies ``omnimarket.nodes.node_emit_daemon``
    is importable under the chosen interpreter, then ``exec``'s the daemon —
    both the import check and daemon startup run off the hook's critical
    path, so the hook never blocks on them.
  - ``--kafka-bootstrap-servers`` is ALWAYS passed (default
    ``localhost:19092``): a daemon started without it runs spool-only (ACKs
    events, forwards nothing to Kafka), which is a silent-drop trap rather
    than a degrade.
  - Degrades to a clean no-op when no suitable interpreter or registry is
    available, and on any exception: hooks keep working without emission.
    Never raises.

The hooks themselves stay stdlib-only; omnimarket (and its pydantic/Kafka
stack) lives exclusively in the daemon's interpreter.

Environment:
  OMNICURSOR_DAEMON_PYTHON  interpreter with omnimarket installed (the bare
                            ``python3`` that runs hooks does NOT have it);
                            fallback: the bundled ``.venv/bin/python``
  OMNICURSOR_EMIT_SOCKET    pinned socket path (default ~/.omnicursor/emit.sock),
                            resolved by the same helper the hooks' emit_client
                            uses, so daemon and hooks always agree
  KAFKA_BOOTSTRAP_SERVERS   Kafka broker (default localhost:19092)
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

from _common import OMNICURSOR_DIR, REPO_ROOT
from emit_client import daemon_available, default_socket_path

_PING_TIMEOUT_S = 0.1
_DEFAULT_KAFKA_BOOTSTRAP = "localhost:19092"
_REGISTRY_PATH: Path = REPO_ROOT / "config" / "event_registry" / "omnicursor.yaml"


def _daemon_python() -> Optional[str]:
    """Resolve the interpreter that runs the daemon (needs omnimarket installed).

    ``OMNICURSOR_DAEMON_PYTHON`` wins when set; a set-but-missing path is an
    explicit misconfiguration and disables the spawn rather than silently
    substituting another interpreter. Fallback: the bundled ``.venv``.
    """
    env = os.environ.get("OMNICURSOR_DAEMON_PYTHON")
    if env:
        p = Path(env).expanduser()
        return str(p) if p.exists() else None
    bundled = REPO_ROOT / ".venv" / "bin" / "python"
    return str(bundled) if bundled.exists() else None


def _kafka_bootstrap_servers() -> str:
    return os.environ.get("KAFKA_BOOTSTRAP_SERVERS") or _DEFAULT_KAFKA_BOOTSTRAP


def _daemon_command(py: str) -> List[str]:
    """The canonical spawn line (Phase-0 P0.5, ratified params)."""
    return [
        py,
        "-m",
        "omnimarket.nodes.node_emit_daemon",
        "start",
        "--socket-path",
        str(default_socket_path()),
        "--pid-path",
        str(OMNICURSOR_DIR / "emit.pid"),
        "--kafka-bootstrap-servers",
        _kafka_bootstrap_servers(),
        "--spool-dir",
        str(OMNICURSOR_DIR / "event-spool"),
        "--event-registry",
        str(_REGISTRY_PATH),
        "--log-path",
        str(OMNICURSOR_DIR / "logs" / "emit-daemon.log"),
    ]


def _clean_env() -> dict:
    """Daemon env without the hook's PYTHONPATH (donor parity: never leak
    hook-side paths into the daemon interpreter)."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _ensure_daemon_dirs() -> None:
    """Pre-create the dirs the daemon writes to, owner-only.

    The daemon's rotating log handler opens ``--log-path`` eagerly and does
    not create parent directories; without ``logs/`` it would die before
    logging anything. The socket's parent dir is created by the daemon itself.
    Spooled payloads can contain raw prompt text, so the state dirs are
    tightened to 0o700 (best-effort).
    """
    for d in (OMNICURSOR_DIR, OMNICURSOR_DIR / "logs", OMNICURSOR_DIR / "event-spool"):
        d.mkdir(parents=True, exist_ok=True)
        try:
            d.chmod(0o700)
        except OSError:
            pass


def _spawn_detached(py: str) -> None:
    """Spawn ``import-check && exec daemon`` fully detached; never waited on.

    The omnimarket import check takes seconds under a cold interpreter, so it
    runs inside the detached child, not in the hook process: a misconfigured
    interpreter degrades to "nothing starts" without ever blocking the hook.
    Failures stay diagnosable: both the import check's stderr and the daemon's
    early-startup stderr (before its own ``--log-path`` handler takes over)
    append to ``logs/spawn.log`` instead of vanishing into /dev/null.
    """
    spawn_log = shlex.quote(str(OMNICURSOR_DIR / "logs" / "spawn.log"))
    import_check = "{} -c {} >/dev/null 2>>{}".format(
        shlex.quote(py),
        shlex.quote("import omnimarket.nodes.node_emit_daemon"),
        spawn_log,
    )
    daemon_cmd = " ".join(shlex.quote(a) for a in _daemon_command(py))
    subprocess.Popen(
        ["/bin/sh", "-c", f"{import_check} && exec {daemon_cmd} 2>>{spawn_log}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=_clean_env(),
        cwd=str(Path.home()),
    )


def ensure_daemon(*, ping_timeout_s: float = _PING_TIMEOUT_S) -> bool:
    """Ensure the shared emit daemon owns the pinned socket.

    Returns True when a daemon answered the liveness ping; False otherwise —
    a detached spawn may have been kicked off, in which case availability
    lands on a later hook (readiness is never waited on here). Never raises;
    never blocks beyond the fast ping.
    """
    try:
        if daemon_available(timeout_s=ping_timeout_s):
            return True
        py = _daemon_python()
        if not py or not _REGISTRY_PATH.exists():
            return False
        _ensure_daemon_dirs()
        _spawn_detached(py)
    except Exception:
        pass
    return False

"""Tests for .cursor/hooks/lib/daemon_ensure.py — shared-daemon provisioning.

Phase 1 A2 contract: fast ping → detached spawn; never blocks the hook; always
passes --kafka-bootstrap-servers; pins the daemon to the same socket the hooks
read; degrades to a clean no-op (no interpreter / no registry / any exception).
No live daemon or infrastructure required — the spawn is captured, never run.
"""

from __future__ import annotations

import importlib.util as _ilu
import shlex
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / ".cursor" / "hooks" / "lib"
sys.path.insert(0, str(_LIB))  # lib modules import each other by bare name


def _load(name: str, path: Path) -> Any:
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_load("_common", _LIB / "_common.py")
_load("emit_client", _LIB / "emit_client.py")
_mod = _load("daemon_ensure", _LIB / "daemon_ensure.py")


class _FakeProc:
    pid = 4242


@pytest.fixture
def hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Dict[str, List[Any]]:
    """Daemon down, state dirs in tmp, interpreter configured, Popen captured."""
    pings: List[Any] = []
    popen_calls: List[Tuple[Any, Dict[str, Any]]] = []

    def _fake_ping(**kwargs: Any) -> bool:
        pings.append(kwargs.get("timeout_s"))
        return False

    def _fake_popen(argv: Any, **kwargs: Any) -> _FakeProc:
        popen_calls.append((argv, kwargs))
        return _FakeProc()

    monkeypatch.setattr(_mod, "daemon_available", _fake_ping)
    monkeypatch.setattr(_mod.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(_mod, "OMNICURSOR_DIR", tmp_path / ".omnicursor")
    monkeypatch.setenv("OMNICURSOR_DAEMON_PYTHON", sys.executable)
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
    monkeypatch.delenv("OMNICURSOR_EMIT_SOCKET", raising=False)
    return {"pings": pings, "popen": popen_calls}


def _wrapper(popen_calls: List[Tuple[Any, Dict[str, Any]]]) -> str:
    """The /bin/sh -c command string of the captured spawn."""
    argv, _ = popen_calls[0]
    assert argv[0] == "/bin/sh" and argv[1] == "-c"
    return argv[2]


class TestFastPath:
    def test_returns_true_without_spawn_when_daemon_up(
        self, hermetic: Dict[str, List[Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "daemon_available", lambda **k: True)
        assert _mod.ensure_daemon() is True
        assert hermetic["popen"] == []

    def test_ping_uses_short_timeout(self, hermetic: Dict[str, List[Any]]) -> None:
        _mod.ensure_daemon()
        assert hermetic["pings"] and hermetic["pings"][0] <= 0.25


class TestSpawn:
    def test_spawns_detached_with_devnull_streams(
        self, hermetic: Dict[str, List[Any]]
    ) -> None:
        assert _mod.ensure_daemon() is False  # spawn kicked off, not waited on
        assert len(hermetic["popen"]) == 1
        _, kwargs = hermetic["popen"][0]
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] == _mod.subprocess.DEVNULL
        assert kwargs["stdout"] == _mod.subprocess.DEVNULL
        assert kwargs["stderr"] == _mod.subprocess.DEVNULL

    def test_wrapper_import_checks_then_execs_daemon(
        self, hermetic: Dict[str, List[Any]]
    ) -> None:
        _mod.ensure_daemon()
        wrapper = _wrapper(hermetic["popen"])
        check_part, _, exec_part = wrapper.partition("&&")
        assert "import omnimarket.nodes.node_emit_daemon" in check_part
        assert "exec" in exec_part
        assert "-m omnimarket.nodes.node_emit_daemon start" in exec_part

    def test_wrapper_stderr_appends_to_spawn_log(
        self, hermetic: Dict[str, List[Any]]
    ) -> None:
        # Import-check and early daemon failures must stay diagnosable: both
        # halves of the wrapper redirect stderr into logs/spawn.log.
        _mod.ensure_daemon()
        wrapper = _wrapper(hermetic["popen"])
        check_part, _, exec_part = wrapper.partition("&&")
        assert check_part.count("2>>") == 1 and "spawn.log" in check_part
        assert exec_part.count("2>>") == 1 and "spawn.log" in exec_part

    def test_kafka_bootstrap_always_passed_with_default(
        self, hermetic: Dict[str, List[Any]]
    ) -> None:
        _mod.ensure_daemon()
        wrapper = _wrapper(hermetic["popen"])
        assert "--kafka-bootstrap-servers localhost:19092" in wrapper

    def test_kafka_bootstrap_env_override(
        self, hermetic: Dict[str, List[Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker.example:9092")
        _mod.ensure_daemon()
        assert "--kafka-bootstrap-servers broker.example:9092" in _wrapper(
            hermetic["popen"]
        )

    def test_socket_pinned_to_hook_default(
        self, hermetic: Dict[str, List[Any]]
    ) -> None:
        _mod.ensure_daemon()
        pinned = shlex.quote(str(Path.home() / ".omnicursor" / "emit.sock"))
        assert f"--socket-path {pinned}" in _wrapper(hermetic["popen"])

    def test_socket_env_override_reaches_daemon_side(
        self,
        hermetic: Dict[str, List[Any]],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        custom = tmp_path / "custom.sock"
        monkeypatch.setenv("OMNICURSOR_EMIT_SOCKET", str(custom))
        _mod.ensure_daemon()
        # R2 regression: the daemon is pinned to the exact socket hooks read.
        assert f"--socket-path {shlex.quote(str(custom))}" in _wrapper(
            hermetic["popen"]
        )

    def test_event_registry_points_at_fork_yaml(
        self, hermetic: Dict[str, List[Any]]
    ) -> None:
        _mod.ensure_daemon()
        registry = shlex.quote(
            str(_ROOT / "config" / "event_registry" / "omnicursor.yaml")
        )
        assert f"--event-registry {registry}" in _wrapper(hermetic["popen"])

    def test_daemon_env_has_no_pythonpath(
        self, hermetic: Dict[str, List[Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PYTHONPATH", "/somewhere/hooks/lib")
        _mod.ensure_daemon()
        _, kwargs = hermetic["popen"][0]
        assert "PYTHONPATH" not in kwargs["env"]

    def test_creates_daemon_state_dirs(
        self, hermetic: Dict[str, List[Any]], tmp_path: Path
    ) -> None:
        _mod.ensure_daemon()
        assert (tmp_path / ".omnicursor" / "logs").is_dir()
        assert (tmp_path / ".omnicursor" / "event-spool").is_dir()

    def test_state_dirs_are_owner_only(
        self, hermetic: Dict[str, List[Any]], tmp_path: Path
    ) -> None:
        # Spooled payloads can contain raw prompt text — 0o700, no group/other.
        _mod.ensure_daemon()
        for d in (".omnicursor", ".omnicursor/logs", ".omnicursor/event-spool"):
            assert ((tmp_path / d).stat().st_mode & 0o777) == 0o700


class TestDegrade:
    def test_no_interpreter_no_spawn(
        self,
        hermetic: Dict[str, List[Any]],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("OMNICURSOR_DAEMON_PYTHON", raising=False)
        monkeypatch.setattr(_mod, "REPO_ROOT", tmp_path)  # no bundled .venv either
        assert _mod.ensure_daemon() is False
        assert hermetic["popen"] == []

    def test_set_but_missing_interpreter_no_spawn(
        self, hermetic: Dict[str, List[Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Explicit misconfiguration disables the spawn rather than silently
        # substituting another interpreter.
        monkeypatch.setenv("OMNICURSOR_DAEMON_PYTHON", "/nope/python")
        assert _mod.ensure_daemon() is False
        assert hermetic["popen"] == []

    def test_missing_registry_no_spawn(
        self,
        hermetic: Dict[str, List[Any]],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(_mod, "_REGISTRY_PATH", tmp_path / "absent.yaml")
        assert _mod.ensure_daemon() is False
        assert hermetic["popen"] == []

    def test_popen_exception_swallowed(
        self, hermetic: Dict[str, List[Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*a: Any, **k: Any) -> None:
            raise RuntimeError("spawn exploded")

        monkeypatch.setattr(_mod.subprocess, "Popen", _boom)
        assert _mod.ensure_daemon() is False  # never raises

    def test_ping_exception_swallowed(
        self, hermetic: Dict[str, List[Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(**k: Any) -> bool:
            raise OSError("socket exploded")

        monkeypatch.setattr(_mod, "daemon_available", _boom)
        assert _mod.ensure_daemon() is False


class TestSpawnDedupe:
    """The O_EXCL spawn stamp throttles detached launches (CodeRabbit, PR #6):
    back-to-back hook invocations must not each spawn a wrapper while the
    daemon is still coming up."""

    def test_second_ensure_within_ttl_does_not_respawn(
        self, hermetic: Dict[str, List[Any]]
    ) -> None:
        assert _mod.ensure_daemon() is False
        assert _mod.ensure_daemon() is False
        assert len(hermetic["popen"]) == 1  # fresh stamp deduped the 2nd spawn

    def test_stale_stamp_allows_respawn(
        self, hermetic: Dict[str, List[Any]], tmp_path: Path
    ) -> None:
        _mod.ensure_daemon()
        stamp = tmp_path / ".omnicursor" / "emit-daemon.spawn.stamp"
        assert stamp.exists()
        old = time.time() - (_mod._SPAWN_STAMP_TTL_S + 5)
        import os as _os

        _os.utime(stamp, (old, old))
        _mod.ensure_daemon()
        assert len(hermetic["popen"]) == 2  # crashed/failed spawn can retry

    def test_stamp_is_owner_only(
        self, hermetic: Dict[str, List[Any]], tmp_path: Path
    ) -> None:
        _mod.ensure_daemon()
        stamp = tmp_path / ".omnicursor" / "emit-daemon.spawn.stamp"
        assert (stamp.stat().st_mode & 0o777) == 0o600

    def test_unexpected_fs_error_fails_open(self, tmp_path: Path) -> None:
        # A stamp path whose parent doesn't exist raises FileNotFoundError —
        # the claim fails OPEN (spawn allowed): dedupe is an optimization,
        # never an availability gate.
        missing = tmp_path / "no-such-dir" / "stamp"
        assert _mod._claim_spawn_stamp(missing) is True

    def test_fresh_stamp_claim_returns_false(self, tmp_path: Path) -> None:
        stamp = tmp_path / "stamp"
        assert _mod._claim_spawn_stamp(stamp) is True  # first claim wins
        assert _mod._claim_spawn_stamp(stamp) is False  # fresh stamp backs off


class TestNonBlocking:
    def test_returns_fast_on_spawn_path(self, hermetic: Dict[str, List[Any]]) -> None:
        start = time.monotonic()
        _mod.ensure_daemon()
        elapsed = time.monotonic() - start
        # Ping is stubbed and the spawn is captured: everything left on the
        # hook's critical path must be effectively instant.
        assert elapsed < 0.5

    def test_spawn_is_never_waited_on(
        self, hermetic: Dict[str, List[Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        waited: List[str] = []

        class _Proc:
            pid = 4242

            def wait(self, *a: Any, **k: Any) -> int:
                waited.append("wait")
                return 0

            def communicate(self, *a: Any, **k: Any) -> Tuple[bytes, bytes]:
                waited.append("communicate")
                return (b"", b"")

        monkeypatch.setattr(_mod.subprocess, "Popen", lambda *a, **k: _Proc())
        _mod.ensure_daemon()
        assert waited == []

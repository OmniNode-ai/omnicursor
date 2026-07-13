"""Tests for .cursor/hooks/scripts/session-start.py — session init + injection.

The sessionStart hook initializes session state, best-effort daemon-ensures +
syncs patterns (local only), injects session-level context via additional_context,
and emits the ``session.started`` registry key.
"""

from __future__ import annotations

import importlib.util as _ilu
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / ".cursor" / "hooks" / "lib"
_SCRIPTS = _ROOT / ".cursor" / "hooks" / "scripts"
sys.path.insert(0, str(_LIB))  # lib modules import each other by bare name


def _load(name: str, path: Path) -> Any:
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_load("_common", _LIB / "_common.py")
_load("pattern_loader", _LIB / "pattern_loader.py")
_load("context_injection", _LIB / "context_injection.py")
_mod = _load("session_start", _SCRIPTS / "session-start.py")


@pytest.fixture
def hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> List[Tuple[str, Dict]]:
    """Isolate session state; stub network/socket; capture emitted events."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
    monkeypatch.setattr(_mod, "log_event", lambda _: None)
    monkeypatch.setattr(_mod, "ensure_daemon", lambda *a, **k: True)
    monkeypatch.setattr(_mod, "sync_learned_patterns", lambda *a, **k: True)
    monkeypatch.setattr(_mod, "fetch_patterns", lambda *a, **k: [])
    monkeypatch.setattr(_mod, "load_prior_session_summary", lambda *a, **k: None)
    emitted: List[Tuple[str, Dict]] = []
    monkeypatch.setattr(
        _mod,
        "send_event",
        lambda topic, payload: emitted.append((topic, payload)) or True,
    )
    return emitted


def _run(monkeypatch: pytest.MonkeyPatch, payload: Dict[str, Any]) -> Dict[str, Any]:
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "stdout", out)
    _mod.main()
    return json.loads(out.getvalue())


class TestInitSession:
    def test_writes_current_json(
        self, hermetic: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _mod._init_session("conv-1", "2026-07-01T00:00:00+00:00")
        current = _mod.SESSIONS_DIR / "current.json"
        data = json.loads(current.read_text())
        assert data["conversation_id"] == "conv-1"
        assert data["started_at"] == "2026-07-01T00:00:00+00:00"

    def test_writes_session_json(self, hermetic: list) -> None:
        _mod._init_session("conv-2", "2026-07-01T00:00:00+00:00")
        data = json.loads((_mod.SESSIONS_DIR / "conv-2.json").read_text())
        assert data["conversation_id"] == "conv-2"
        assert data["ci_passing"] is False

    def test_empty_conv_id_does_not_crash(self, hermetic: list) -> None:
        _mod._init_session("", "2026-07-01T00:00:00+00:00")


class TestMainInjection:
    def test_outputs_additional_context(
        self, hermetic: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = _run(monkeypatch, {"conversation_id": "c1", "session_id": "s1"})
        assert "additional_context" in out
        assert "Delegation Rule" in out["additional_context"]

    def test_injects_patterns_when_available(
        self, hermetic: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            _mod,
            "fetch_patterns",
            lambda *a, **k: [{"pattern_id": "p1", "description": "DI"}],
        )
        out = _run(monkeypatch, {"conversation_id": "c1"})
        assert "p1" in out["additional_context"]

    def test_injects_prior_session_block(
        self, hermetic: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            _mod,
            "load_prior_session_summary",
            lambda *a, **k: {"session_outcome": "success", "files_edited": 3},
        )
        out = _run(monkeypatch, {"conversation_id": "c1"})
        assert "Prior Session Context" in out["additional_context"]

    def test_emits_session_started(
        self, hermetic: List[Tuple[str, Dict]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _run(monkeypatch, {"conversation_id": "c1", "session_id": "s1"})
        # Semantic registry key (stop.py pattern) — never a topic literal.
        events = {t: p for t, p in hermetic}
        assert "session.started" in events
        payload = events["session.started"]
        assert payload["session_id"] == "c1"
        assert payload["cursor_session_id"] == "s1"
        assert payload["agent_source"] == "cursor"

    def test_no_topic_literal_emitted(
        self, hermetic: List[Tuple[str, Dict]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _run(monkeypatch, {"conversation_id": "c1", "session_id": "s1"})
        assert all(not t.startswith("onex.") for t, _ in hermetic)

    def test_empty_stdin_still_outputs_json(
        self, hermetic: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        # Empty stdin → still valid JSON (delegation rule always injected).
        assert "additional_context" in json.loads(out.getvalue())


class TestBackgroundAgentDegrade:
    def test_background_agent_skips_daemon_and_sync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
        monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        monkeypatch.setattr(_mod, "fetch_patterns", lambda *a, **k: [])
        monkeypatch.setattr(_mod, "load_prior_session_summary", lambda *a, **k: None)
        monkeypatch.setattr(_mod, "send_event", lambda *a, **k: True)

        calls: List[str] = []
        monkeypatch.setattr(
            _mod, "ensure_daemon", lambda *a, **k: calls.append("daemon") or True
        )
        monkeypatch.setattr(
            _mod, "sync_learned_patterns", lambda *a, **k: calls.append("sync") or True
        )

        out = _run(monkeypatch, {"conversation_id": "c1", "is_background_agent": True})
        assert calls == []  # neither daemon-ensure nor sync ran
        assert "additional_context" in out  # but injection still attempted


class TestDaemonEnsureTrigger:
    """sessionStart is the primary daemon-ensure trigger (Phase 1 A2)."""

    def test_local_session_calls_ensure_daemon(
        self, hermetic: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: List[str] = []
        monkeypatch.setattr(
            _mod, "ensure_daemon", lambda *a, **k: calls.append("ensure") or True
        )
        _run(monkeypatch, {"conversation_id": "c1", "session_id": "s1"})
        assert calls == ["ensure"]

    def test_ensure_result_logged_as_daemon_available(
        self, hermetic: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        logged: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: logged.append(e))
        monkeypatch.setattr(_mod, "ensure_daemon", lambda *a, **k: True)
        _run(monkeypatch, {"conversation_id": "c1"})
        assert logged and logged[0]["daemon_available"] is True

    def test_ensure_exception_degrades_to_unavailable(
        self, hermetic: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        logged: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: logged.append(e))

        def _boom(*a: object, **k: object) -> bool:
            raise RuntimeError("ensure exploded")

        monkeypatch.setattr(_mod, "ensure_daemon", _boom)
        out = _run(monkeypatch, {"conversation_id": "c1"})
        assert logged and logged[0]["daemon_available"] is False
        assert "additional_context" in out  # hook still completes + injects

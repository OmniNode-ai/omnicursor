"""Tests for .cursor/hooks/scripts/session-end.py — true session-close event.

Fire-and-forget: outputs {} and emits the ``session.ended`` registry key
(the registry YAML owns the topic string).
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
_mod = _load("session_end", _SCRIPTS / "session-end.py")


@pytest.fixture
def emitted(monkeypatch: pytest.MonkeyPatch) -> List[Tuple[str, Dict]]:
    events: List[Tuple[str, Dict]] = []
    monkeypatch.setattr(_mod, "log_event", lambda _: None)
    monkeypatch.setattr(_mod, "read_session_context", lambda: {})
    monkeypatch.setattr(
        _mod,
        "send_event",
        lambda topic, payload: events.append((topic, payload)) or True,
    )
    return events


def _run(monkeypatch: pytest.MonkeyPatch, payload: Dict[str, Any]) -> Dict[str, Any]:
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "stdout", out)
    _mod.main()
    return json.loads(out.getvalue())


class TestSessionEnd:
    def test_outputs_empty_dict(
        self, emitted: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = _run(monkeypatch, {"conversation_id": "c1", "reason": "user_close"})
        assert out == {}

    def test_emits_session_ended(
        self, emitted: List[Tuple[str, Dict]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _run(
            monkeypatch,
            {
                "conversation_id": "c1",
                "session_id": "s1",
                "reason": "completed",
                "duration_ms": 4200,
                "final_status": "completed",
            },
        )
        assert len(emitted) == 1
        topic, payload = emitted[0]
        # Semantic registry key (stop.py pattern) — never a topic literal.
        assert topic == "session.ended"
        assert payload["session_id"] == "c1"
        assert payload["cursor_session_id"] == "s1"
        assert payload["agent_source"] == "cursor"
        assert payload["reason"] == "completed"
        assert payload["final_status"] == "completed"
        assert payload["duration_ms"] == 4200

    def test_empty_stdin_still_outputs_empty_dict(
        self, emitted: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        assert json.loads(out.getvalue()) == {}

    def test_error_message_is_redacted_before_emit(
        self, emitted: List[Tuple[str, Dict]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # error_message comes straight from hook input and often carries
        # tokens/creds — it must pass through redact_secrets before emission
        # (A5; CodeRabbit Major on PR #6).
        _run(
            monkeypatch,
            {
                "conversation_id": "c1",
                "reason": "error",
                "final_status": "failed",
                "error_message": "login failed: password=supersecret123 retry later",
            },
        )
        _, payload = emitted[0]
        assert "supersecret123" not in payload["error_message"]
        assert "***REDACTED***" in payload["error_message"]

    def test_absent_error_message_emits_none(
        self, emitted: List[Tuple[str, Dict]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _run(monkeypatch, {"conversation_id": "c1", "reason": "user_close"})
        _, payload = emitted[0]
        assert payload["error_message"] is None

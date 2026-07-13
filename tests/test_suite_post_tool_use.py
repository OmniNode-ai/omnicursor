"""Tests for .cursor/hooks/scripts/post-tool-use.py — mid-session refresh.

postToolUse infers a domain from the tool's file path, refreshes learned patterns
via additional_context, and emits the ``tool.executed`` registry key.
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
_mod = _load("post_tool_use", _SCRIPTS / "post-tool-use.py")


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


class TestFilePathExtraction:
    def test_file_path_key(self) -> None:
        assert _mod._tool_file_path({"file_path": "a.py"}) == "a.py"

    def test_target_file_key(self) -> None:
        assert _mod._tool_file_path({"target_file": "b.ts"}) == "b.ts"

    def test_non_dict_returns_empty(self) -> None:
        assert _mod._tool_file_path("nope") == ""


class TestRefresh:
    def test_injects_when_patterns_available(
        self, emitted: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: Dict[str, Any] = {}
        monkeypatch.setattr(
            _mod,
            "fetch_patterns",
            lambda domain, **k: (
                captured.update(domain=domain)
                or [{"pattern_id": "p1", "description": "thin nodes"}]
            ),
        )
        out = _run(
            monkeypatch,
            {
                "conversation_id": "c1",
                "tool_name": "edit_file",
                "tool_input": {"file_path": "src/app.py"},
            },
        )
        assert captured["domain"] == "python"  # inferred from .py
        assert "p1" in out["additional_context"]

    def test_empty_output_when_no_patterns(
        self, emitted: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "fetch_patterns", lambda *a, **k: [])
        out = _run(
            monkeypatch,
            {
                "conversation_id": "c1",
                "tool_name": "edit_file",
                "tool_input": {"file_path": "x.py"},
            },
        )
        assert out == {}

    def test_emits_tool_executed(
        self, emitted: List[Tuple[str, Dict]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "fetch_patterns", lambda *a, **k: [])
        _run(
            monkeypatch,
            {
                "conversation_id": "c1",
                "tool_name": "edit_file",
                "tool_input": {"file_path": "x.py"},
            },
        )
        # Semantic registry key (stop.py pattern) — never a topic literal.
        events = {t: p for t, p in emitted}
        assert "tool.executed" in events
        payload = events["tool.executed"]
        assert payload["session_id"] == "c1"
        assert payload["tool_name"] == "edit_file"
        assert payload["agent_source"] == "cursor"
        assert all(not t.startswith("onex.") for t in events)

    def test_empty_stdin_does_not_crash(
        self, emitted: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "fetch_patterns", lambda *a, **k: [])
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        assert json.loads(out.getvalue()) == {}

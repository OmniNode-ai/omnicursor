"""Tests for hooks lib emit_client (no live socket required)."""

from __future__ import annotations

import importlib.util as ilu
import sys
from pathlib import Path

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


def test_send_event_false_when_socket_missing(
    emit_mod, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(emit_mod, "default_socket_path", lambda: tmp_path / "nope.sock")
    assert emit_mod.send_event("onex.test.v1", {"a": 1}) is False

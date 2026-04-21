"""Tests for omnicursor.sync.pattern_sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from omnicursor.sync.pattern_sync import run


def test_run_writes_list_response(tmp_path: Path) -> None:
    target = tmp_path / "learned.json"
    payload = [{"pattern_id": "p1", "domain": "test", "description": "d"}]
    raw = json.dumps(payload).encode()

    class _Resp:
        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def read(self) -> bytes:
            return raw

    def fake_urlopen(*_a, **_kw):  # type: ignore[no-untyped-def]
        return _Resp()

    with mock.patch("omnicursor.sync.pattern_sync.urllib.request.urlopen", fake_urlopen):
        assert run(target, base_url="http://example.invalid", timeout_s=1.0) is True
    data = json.loads(target.read_text())
    assert data["patterns"] == payload


def test_run_writes_dict_with_patterns_key(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    body = {"patterns": [{"pattern_id": "x"}]}
    raw = json.dumps(body).encode()

    class _Resp:
        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def read(self) -> bytes:
            return raw

    def fake_urlopen(*_a, **_kw):  # type: ignore[no-untyped-def]
        return _Resp()

    with mock.patch("omnicursor.sync.pattern_sync.urllib.request.urlopen", fake_urlopen):
        assert run(target, base_url="http://example.invalid") is True
    assert json.loads(target.read_text()) == body


def test_run_returns_false_on_network_error(tmp_path: Path) -> None:
    target = tmp_path / "missing.json"
    with mock.patch(
        "omnicursor.sync.pattern_sync.urllib.request.urlopen",
        side_effect=OSError("no network"),
    ):
        assert run(target, base_url="http://127.0.0.1:1", timeout_s=0.1) is False
    assert not target.exists()

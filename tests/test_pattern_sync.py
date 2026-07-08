"""Tests for omnicursor.sync.pattern_sync."""

from __future__ import annotations

import importlib.util
import json
import urllib.error
from pathlib import Path
from unittest import mock

from omnicursor.sync.pattern_sync import run


def test_run_uses_default_base_url_port_18091(tmp_path: Path) -> None:
    target = tmp_path / "learned.json"
    captured: dict[str, str] = {}
    raw = json.dumps({"patterns": []}).encode()

    class _Resp:
        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def read(self) -> bytes:
            return raw

    def fake_urlopen(req, **_kw):  # type: ignore[no-untyped-def]
        captured["url"] = req.full_url
        return _Resp()

    with (
        mock.patch.dict("omnicursor.sync.pattern_sync.os.environ", {}, clear=True),
        mock.patch("omnicursor.sync.pattern_sync.urllib.request.urlopen", fake_urlopen),
    ):
        assert run(target, timeout_s=1.0) is True

    # Default host spelling is single-sourced with the hooks' per-prompt fetch
    # (lib/context_injection.py) — localhost, not 127.0.0.1.
    assert captured["url"] == "http://localhost:18091/api/v1/patterns"


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


def test_run_merges_remote_patterns_with_local(tmp_path: Path) -> None:
    target = tmp_path / "learned.json"
    target.write_text(
        json.dumps(
            {
                "patterns": [
                    {"pattern_id": "local-1", "domain": "local"},
                    {"pattern_id": "shared", "domain": "local-shared"},
                ]
            }
        ),
        encoding="utf-8",
    )
    remote = {
        "patterns": [
            {"pattern_id": "shared", "domain": "remote-should-not-overwrite"},
            {"pattern_id": "remote-1", "domain": "remote"},
        ]
    }
    raw = json.dumps(remote).encode()

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

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["patterns"] == [
        {"pattern_id": "local-1", "domain": "local"},
        {"pattern_id": "shared", "domain": "local-shared"},
        {"pattern_id": "remote-1", "domain": "remote"},
    ]


def test_run_returns_false_on_network_error(tmp_path: Path) -> None:
    target = tmp_path / "missing.json"
    with mock.patch(
        "omnicursor.sync.pattern_sync.urllib.request.urlopen",
        side_effect=OSError("no network"),
    ):
        assert run(target, base_url="http://127.0.0.1:1", timeout_s=0.1) is False
    assert not target.exists()


def test_run_keeps_local_file_when_network_unavailable(tmp_path: Path) -> None:
    target = tmp_path / "learned.json"
    local = {"patterns": [{"pattern_id": "local-only"}]}
    target.write_text(json.dumps(local), encoding="utf-8")

    with mock.patch(
        "omnicursor.sync.pattern_sync.urllib.request.urlopen",
        side_effect=OSError("no network"),
    ):
        assert run(target, base_url="http://127.0.0.1:1", timeout_s=0.1) is False

    assert json.loads(target.read_text(encoding="utf-8")) == local


def test_run_offline_falls_back_to_local_only_without_raising(tmp_path: Path) -> None:
    target = tmp_path / "learned.json"
    local = {"patterns": [{"pattern_id": "local-a"}, {"pattern_id": "local-b"}]}
    target.write_text(json.dumps(local), encoding="utf-8")

    with mock.patch(
        "omnicursor.sync.pattern_sync.urllib.request.urlopen",
        side_effect=urllib.error.URLError("offline"),
    ):
        result = run(target, base_url="http://127.0.0.1:18091", timeout_s=0.1)

    assert result is False
    assert json.loads(target.read_text(encoding="utf-8")) == local


# ---------------------------------------------------------------------------
# Defensive behaviour — new in Option B mínima
# ---------------------------------------------------------------------------

class _Resp:
    """Minimal urlopen context-manager stub."""

    def __init__(self, body: bytes = b"[]") -> None:
        self._body = body

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class TestPatternSyncDefensive:
    def test_health_probe_fails_offline_returns_false_no_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        with mock.patch(
            "omnicursor.sync.pattern_sync.urllib.request.urlopen",
            side_effect=OSError("refused"),
        ):
            assert run(target, base_url="http://127.0.0.1:1", timeout_s=0.1) is False
        assert not target.exists()

    def test_health_ok_patterns_404_returns_false_preserves_existing(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "out.json"
        original = {"patterns": [{"pattern_id": "keep"}]}
        target.write_text(json.dumps(original))
        call_count = [0]

        def _two_calls(req: object, **_kw: object) -> "_Resp":
            call_count[0] += 1
            if call_count[0] == 1:
                return _Resp(b"{}")  # /health succeeds
            raise urllib.error.HTTPError(  # /api/v1/patterns → 404
                url="http://x/api/v1/patterns",
                code=404,
                msg="Not Found",
                hdrs={},  # type: ignore[arg-type]
                fp=None,
            )

        with mock.patch("omnicursor.sync.pattern_sync.urllib.request.urlopen", _two_calls):
            assert run(target, base_url="http://x", timeout_s=1.0) is False
        assert json.loads(target.read_text()) == original

    def test_unexpected_body_returns_false_preserves_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        original = {"patterns": [{"pattern_id": "keep"}]}
        target.write_text(json.dumps(original))

        # Both calls (health + patterns) return unexpected body
        with mock.patch(
            "omnicursor.sync.pattern_sync.urllib.request.urlopen",
            lambda *_a, **_kw: _Resp(b'{"not_patterns": 42}'),
        ):
            assert run(target, base_url="http://x", timeout_s=1.0) is False
        assert json.loads(target.read_text()) == original

    def test_env_intelligence_service_url_takes_precedence(
        self, tmp_path: Path, monkeypatch: mock.MagicMock
    ) -> None:
        """INTELLIGENCE_SERVICE_URL (the hooks' var) wins over the deprecated name."""
        target = tmp_path / "out.json"
        captured: list[str] = []

        def _capture(req: urllib.request.Request, **_kw: object) -> "_Resp":
            captured.append(req.full_url)
            return _Resp(b"[]")

        monkeypatch.setenv("INTELLIGENCE_SERVICE_URL", "http://primary-host:1111")
        monkeypatch.setenv("OMNIINTELLIGENCE_URL", "http://legacy-host:9999")
        with mock.patch("omnicursor.sync.pattern_sync.urllib.request.urlopen", _capture):
            run(target, timeout_s=1.0)
        assert all("primary-host:1111" in u for u in captured)

    def test_env_omniintelligence_url_deprecated_fallback(
        self, tmp_path: Path, monkeypatch: mock.MagicMock
    ) -> None:
        """The old OMNIINTELLIGENCE_URL still works (deprecated, one release)."""
        target = tmp_path / "out.json"
        captured: list[str] = []

        def _capture(req: urllib.request.Request, **_kw: object) -> "_Resp":
            captured.append(req.full_url)
            return _Resp(b"[]")

        monkeypatch.delenv("INTELLIGENCE_SERVICE_URL", raising=False)
        monkeypatch.setenv("OMNIINTELLIGENCE_URL", "http://custom-host:9999")
        with mock.patch("omnicursor.sync.pattern_sync.urllib.request.urlopen", _capture):
            run(target, timeout_s=1.0)
        assert all("custom-host:9999" in u for u in captured)

    def test_default_url_contains_18091(
        self, tmp_path: Path, monkeypatch: mock.MagicMock
    ) -> None:
        target = tmp_path / "out.json"
        captured: list[str] = []

        def _capture(req: urllib.request.Request, **_kw: object) -> "_Resp":
            captured.append(req.full_url)
            return _Resp(b"[]")

        monkeypatch.delenv("INTELLIGENCE_SERVICE_URL", raising=False)
        monkeypatch.delenv("OMNIINTELLIGENCE_URL", raising=False)
        with mock.patch("omnicursor.sync.pattern_sync.urllib.request.urlopen", _capture):
            run(target, timeout_s=1.0)
        assert all("18091" in u for u in captured)

    def test_successful_write_produces_valid_json(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        body = [{"pattern_id": "p1", "domain": "test", "description": "d"}]
        with mock.patch(
            "omnicursor.sync.pattern_sync.urllib.request.urlopen",
            lambda *_a, **_kw: _Resp(json.dumps(body).encode()),
        ):
            assert run(target, base_url="http://x", timeout_s=1.0) is True
        data = json.loads(target.read_text())
        assert isinstance(data.get("patterns"), list)

    def test_shim_delegates_to_canonical_run(self, tmp_path: Path) -> None:
        """lib/pattern_sync.py shim executes the same logic as the canonical run."""
        shim_path = (
            Path(__file__).parent.parent / ".cursor" / "hooks" / "lib" / "pattern_sync.py"
        )
        spec = importlib.util.spec_from_file_location("_test_shim_ps", shim_path)
        assert spec is not None and spec.loader is not None
        shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shim)  # type: ignore[union-attr]

        target = tmp_path / "shim_out.json"
        body = [{"pattern_id": "s1", "domain": "d"}]
        with mock.patch(
            "omnicursor.sync.pattern_sync.urllib.request.urlopen",
            lambda *_a, **_kw: _Resp(json.dumps(body).encode()),
        ):
            result = shim.sync_learned_patterns(target, timeout_s=1.0)

        assert result is True
        data = json.loads(target.read_text())
        assert data["patterns"] == body

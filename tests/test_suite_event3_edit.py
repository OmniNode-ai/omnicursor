"""Event 3 — afterFileEdit: tests for post-edit.py."""

from __future__ import annotations

import importlib.util as _ilu
import io
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import omnicursor.file_edit as _file_edit  # canonical source; patch subprocess here
import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / ".cursor" / "hooks" / "lib"
_SCRIPTS = _ROOT / ".cursor" / "hooks" / "scripts"


def _load(name: str, path: Path) -> Any:
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod

_lib_common = _load("_common", _LIB / "_common.py")
_mod = _load("post_edit", _SCRIPTS / "post-edit.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeRunResult:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def _ruff_result(output: str, returncode: int = 1) -> _FakeRunResult:
    return _FakeRunResult(stdout=output, returncode=returncode)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


class TestLanguageDetection:
    def test_python(self) -> None:
        assert _mod.detect_language("foo.py") == "python"

    def test_typescript(self) -> None:
        assert _mod.detect_language("bar.ts") == "typescript"

    def test_tsx(self) -> None:
        assert _mod.detect_language("comp.tsx") == "typescript"

    def test_javascript(self) -> None:
        assert _mod.detect_language("app.js") == "javascript"

    def test_jsx(self) -> None:
        assert _mod.detect_language("app.jsx") == "javascript"

    def test_yaml(self) -> None:
        assert _mod.detect_language("config.yaml") == "yaml"

    def test_yml(self) -> None:
        assert _mod.detect_language("config.yml") == "yaml"

    def test_json(self) -> None:
        assert _mod.detect_language("data.json") == "json"

    def test_markdown(self) -> None:
        assert _mod.detect_language("README.md") == "markdown"

    def test_unknown_extension(self) -> None:
        assert _mod.detect_language("binary.wasm") == "other"

    def test_no_extension(self) -> None:
        assert _mod.detect_language("Makefile") == "other"

    def test_case_insensitive(self) -> None:
        assert _mod.detect_language("foo.PY") == "python"

    def test_language_detection_python(self) -> None:
        """Original stub: python extension → 'python'."""
        assert _mod.detect_language("src/main.py") == "python"

    def test_language_detection_typescript(self) -> None:
        """Original stub: .ts extension → 'typescript'."""
        assert _mod.detect_language("src/index.ts") == "typescript"

    def test_language_detection_unknown_extension(self) -> None:
        """Original stub: unrecognised extension → 'other'."""
        assert _mod.detect_language("archive.tar.gz") == "other"


# ---------------------------------------------------------------------------
# Ruff diagnostics
# ---------------------------------------------------------------------------


class TestRuffDiagnostics:
    def test_python_file_triggers_ruff_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: Python file causes ruff to be invoked."""
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        _mod.handle_edit({"file_path": "foo.py", "edits": []})
        assert len(calls) == 1
        assert any(Path(part).name.startswith("ruff") for part in calls[0])

    def test_non_python_file_skips_ruff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-Python file never calls ruff (tsc may still fire for .ts)."""
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        _mod.handle_edit({"file_path": "foo.ts", "edits": []})
        assert all("ruff" not in cmd for cmd in calls)

    def test_ruff_never_runs_fix_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: ruff must never be called with --fix."""
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        _mod.run_ruff_check("foo.py")
        assert len(calls) == 1
        assert "--fix" not in calls[0]

    def test_ruff_called_with_check_subcommand(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        _mod.run_ruff_check("foo.py")
        assert "check" in calls[0]

    def test_ruff_prefers_repo_venv_binary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        ruff = venv_bin / "ruff"
        ruff.write_text("#!/bin/sh\n", encoding="utf-8")
        ruff.chmod(0o755)

        calls: List[Any] = []
        monkeypatch.setattr(_file_edit, "_REPO_ROOT", tmp_path)
        monkeypatch.setattr(_file_edit.shutil, "which", lambda _name: "/usr/bin/ruff")
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())

        _mod.run_ruff_check("foo.py")

        assert calls[0][0] == str(ruff)

    def test_ruff_findings_counted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two output lines → ruff_findings == 2."""
        monkeypatch.setattr(
            _file_edit.subprocess, "run",
            lambda cmd, **kw: _ruff_result("foo.py:1:1: E501 line too long\nfoo.py:2:1: W291 trailing whitespace"),
        )
        result = _mod.run_ruff_check("foo.py")
        assert result == 2

    def test_ruff_findings_zero_on_clean_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: _FakeRunResult(stdout="", returncode=0))
        result = _mod.run_ruff_check("foo.py")
        assert result == 0

    def test_ruff_not_found_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ruff not installed → FileNotFoundError → returns 0, does not crash."""
        monkeypatch.setattr(
            _file_edit.subprocess, "run",
            lambda cmd, **kw: (_ for _ in ()).throw(FileNotFoundError("ruff")),
        )
        result = _mod.run_ruff_check("foo.py")
        assert result == 0

    def test_ruff_timeout_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            _file_edit.subprocess, "run",
            lambda cmd, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("ruff", 5)),
        )
        result = _mod.run_ruff_check("foo.py")
        assert result == 0

    def test_ruff_findings_reflected_in_handle_edit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            _file_edit.subprocess, "run",
            lambda cmd, **kw: _ruff_result("foo.py:1:1: E501 line too long"),
        )
        result = _mod.handle_edit({"file_path": "foo.py", "edits": []})
        assert result["ruff_findings"] == 1

    def test_non_python_ruff_findings_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-Python file has ruff_findings == 0 without calling ruff."""
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        result = _mod.handle_edit({"file_path": "foo.ts", "edits": []})
        assert result["ruff_findings"] == 0


# ---------------------------------------------------------------------------
# TSC diagnostics
# ---------------------------------------------------------------------------


class TestTscDiagnostics:
    def test_typescript_file_triggers_tsc_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        _mod.handle_edit({"file_path": "foo.ts", "edits": []})
        assert len(calls) == 1
        assert "tsc" in calls[0]

    def test_tsx_file_triggers_tsc_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        _mod.handle_edit({"file_path": "comp.tsx", "edits": []})
        assert len(calls) == 1
        assert "tsc" in calls[0]

    def test_non_typescript_file_skips_tsc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        _mod.handle_edit({"file_path": "foo.py", "edits": []})
        assert all("tsc" not in cmd for cmd in calls)

    def test_tsc_called_with_no_emit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        _mod.run_tsc_check("foo.ts")
        assert "--noEmit" in calls[0]

    def test_tsc_findings_counted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = (
            "foo.ts(1,5): error TS2322: Type 'string' is not assignable to type 'number'.\n"
            "foo.ts(3,9): error TS2304: Cannot find name 'bar'.\n"
        )
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: _FakeRunResult(stdout=output, returncode=1))
        result = _mod.run_tsc_check("foo.ts")
        assert result == 2

    def test_tsc_findings_zero_on_clean_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: _FakeRunResult(stdout="", returncode=0))
        result = _mod.run_tsc_check("foo.ts")
        assert result == 0

    def test_tsc_not_found_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            _file_edit.subprocess, "run",
            lambda cmd, **kw: (_ for _ in ()).throw(FileNotFoundError("tsc")),
        )
        result = _mod.run_tsc_check("foo.ts")
        assert result == 0

    def test_tsc_timeout_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            _file_edit.subprocess, "run",
            lambda cmd, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("tsc", 15)),
        )
        result = _mod.run_tsc_check("foo.ts")
        assert result == 0

    def test_tsc_findings_reflected_in_handle_edit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "foo.ts(1,5): error TS2322: Type 'string' is not assignable to type 'number'.\n"
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: _FakeRunResult(stdout=output, returncode=1))
        result = _mod.handle_edit({"file_path": "foo.ts", "edits": []})
        assert result["tsc_findings"] == 1

    def test_non_typescript_tsc_findings_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Any] = []
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _FakeRunResult())
        result = _mod.handle_edit({"file_path": "foo.py", "edits": []})
        assert result["tsc_findings"] == 0
        assert all("tsc" not in cmd for cmd in calls)


# ---------------------------------------------------------------------------
# handle_edit — core behaviour
# ---------------------------------------------------------------------------


class TestHandleEdit:
    def test_returns_event_type(self) -> None:
        result = _mod.handle_edit({"file_path": "a.md", "edits": []})
        assert result["event"] == "file_edited"

    def test_edit_count_from_list(self) -> None:
        edits = [{"line": 1}, {"line": 2}, {"line": 3}]
        result = _mod.handle_edit({"file_path": "a.md", "edits": edits})
        assert result["edit_count"] == 3

    def test_edit_count_empty_list(self) -> None:
        result = _mod.handle_edit({"file_path": "a.md", "edits": []})
        assert result["edit_count"] == 0

    def test_edit_count_missing_key(self) -> None:
        result = _mod.handle_edit({"file_path": "a.md"})
        assert result["edit_count"] == 0

    def test_missing_file_path_does_not_crash(self) -> None:
        """Original stub: absent file_path → language='other', no crash."""
        result = _mod.handle_edit({"edits": []})
        assert result["language"] == "other"
        assert result["file_path"] == ""

    def test_empty_event_does_not_crash(self) -> None:
        """Original stub: completely empty dict → no exception."""
        result = _mod.handle_edit({})
        assert result["event"] == "file_edited"

    def test_multiple_edits_counted_independently(self) -> None:
        """Original stub: edit_count tracks list length."""
        result = _mod.handle_edit({"file_path": "x.py", "edits": [{}, {}, {}, {}]})
        assert result["edit_count"] == 4

    def test_conversation_id_preserved(self) -> None:
        result = _mod.handle_edit({"file_path": "a.py", "edits": [], "conversation_id": "c-xyz"})
        assert result["conversation_id"] == "c-xyz"

    def test_file_path_preserved(self) -> None:
        result = _mod.handle_edit({"file_path": "src/foo.py", "edits": []})
        assert result["file_path"] == "src/foo.py"

    def test_file_path_truncated_at_500(self) -> None:
        long_path = "x" * 600 + ".md"
        result = _mod.handle_edit({"file_path": long_path, "edits": []})
        assert len(result["file_path"]) == 500


# ---------------------------------------------------------------------------
# Correlation threading
# ---------------------------------------------------------------------------


class TestCorrelationThreading:
    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        file_path: str = "foo.md",
        session: Dict = {},
    ) -> Dict:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "read_session_context", lambda: session)
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"file_path": file_path, "edits": [], "conversation_id": "c-001"})
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        return events[0]

    def test_correlation_id_read_from_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, session={"latest_correlation_id": "abc123def456"})
        assert e["correlation_id"] == "abc123def456"

    def test_missing_session_uses_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, session={})
        assert e["correlation_id"] == ""

    def test_correlation_id_on_python_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_file_edit.subprocess, "run", lambda cmd, **kw: _FakeRunResult())
        e = self._run(monkeypatch, file_path="main.py", session={"latest_correlation_id": "py000001abc1"})
        assert e["correlation_id"] == "py000001abc1"

    def test_correlation_id_on_typescript_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, file_path="app.ts", session={"latest_correlation_id": "ts000001abc1"})
        assert e["correlation_id"] == "ts000001abc1"

    def test_extra_session_fields_do_not_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, session={
            "latest_correlation_id": "valid0000001",
            "conversation_id": "c-001",
            "started_at": "2026-04-14T00:00:00+00:00",
        })
        assert e["correlation_id"] == "valid0000001"


# ---------------------------------------------------------------------------
# Typed event schema
# ---------------------------------------------------------------------------


class TestTypedEventSchema:
    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        file_path: str = "foo.md",
        edits: list = [],
        conv: str = "s-001",
    ) -> Dict:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "read_session_context", lambda: {"latest_correlation_id": "test000abc12"})
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"file_path": file_path, "edits": edits, "conversation_id": conv})
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        return events[0]

    def test_event_type_is_file_edited(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["event"] == "file_edited"

    def test_event_has_conversation_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["conversation_id"] == "s-001"

    def test_event_has_correlation_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["correlation_id"] == "test000abc12"

    def test_event_has_file_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["file_path"] == "foo.md"

    def test_event_has_edit_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch, edits=[{}, {}])["edit_count"] == 2

    def test_event_has_language(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch, file_path="foo.ts")["language"] == "typescript"

    def test_event_has_ruff_findings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert "ruff_findings" in self._run(monkeypatch)

    def test_event_has_tsc_findings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert "tsc_findings" in self._run(monkeypatch)

    def test_tsc_findings_zero_for_non_typescript(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, file_path="foo.py")
        assert e["tsc_findings"] == 0

    def test_event_has_hook_duration_ms(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch)
        assert "hook_duration_ms" in e and isinstance(e["hook_duration_ms"], int)

    def test_stdout_is_empty_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cursor ignores afterFileEdit stdout — we always emit {}."""
        import json as _json
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"file_path": "a.md", "edits": []})
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        _mod.main()
        assert _json.loads(buf.getvalue().strip()) == {}

    def test_event_logged_to_events_jsonl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: log_event is called exactly once per edit."""
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"file_path": "x.md", "edits": [], "conversation_id": "t-1"})
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        assert len(events) == 1
        assert events[0]["event"] == "file_edited"
        assert events[0]["conversation_id"] == "t-1"

    def test_ruff_findings_zero_for_non_python(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, file_path="styles.css")
        assert e["ruff_findings"] == 0

    def test_language_other_for_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, file_path="archive.wasm")
        assert e["language"] == "other"


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


class TestRobustness:
    def test_exception_in_main_does_not_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Even if read_stdin raises, main() exits cleanly and emits {}."""
        import json as _json
        monkeypatch.setattr(_mod, "read_stdin", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        _mod.main()
        assert _json.loads(buf.getvalue().strip()) == {}

    def test_non_list_edits_gives_zero_count(self) -> None:
        result = _mod.handle_edit({"file_path": "a.md", "edits": "not-a-list"})
        assert result["edit_count"] == 0

    def test_none_file_path_does_not_crash(self) -> None:
        result = _mod.handle_edit({"file_path": None, "edits": []})
        assert result["event"] == "file_edited"

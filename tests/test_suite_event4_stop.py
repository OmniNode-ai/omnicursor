"""Event 4 — stop: tests for stop.py."""

from __future__ import annotations

import importlib.util as _ilu
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

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
_mod = _load("stop", _SCRIPTS / "stop.py")


def _stub_stop_emit_and_pattern_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 1: stop.py emits on socket + syncs patterns — stub for isolated tests."""
    monkeypatch.setattr(_mod, "send_event", lambda *a, **k: False)
    monkeypatch.setattr(_mod, "sync_learned_patterns", lambda *a, **k: False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_type: str,
    conversation_id: str = "c-001",
    timestamp: str = "2026-04-14T10:00:00+00:00",
    **kwargs: Any,
) -> Dict[str, Any]:
    return {"event": event_type, "conversation_id": conversation_id, "timestamp": timestamp, **kwargs}


def _write_events(path: Path, events: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


# ---------------------------------------------------------------------------
# Outcome classification — pure function, no I/O
# ---------------------------------------------------------------------------


class TestOutcomeClassification:
    def test_gate_1_failed_on_error_status(self) -> None:
        """Original stub: status='failed' → outcome 'failed'."""
        outcome, _ = _mod.derive_session_outcome("failed", [])
        assert outcome == "failed"

    def test_gate_1_failed_on_aborted_status(self) -> None:
        outcome, _ = _mod.derive_session_outcome("aborted", [])
        assert outcome == "failed"

    def test_gate_1_failed_on_error_status_string(self) -> None:
        outcome, _ = _mod.derive_session_outcome("error", [])
        assert outcome == "failed"

    def test_gate_1_failed_on_traceback_in_events(self) -> None:
        events = [_make_event("prompt_classified", reason="Traceback (most recent call last)")]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome == "failed"

    def test_gate_1_failed_on_exception_marker(self) -> None:
        events = [_make_event("prompt_classified", reason="ValueError: bad input")]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome == "failed"

    def test_gate_1_failed_on_n_failed_marker(self) -> None:
        events = [_make_event("prompt_classified", reason="3 FAILED")]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome == "failed"

    def test_gate_1_zero_failed_not_counted(self) -> None:
        """'0 FAILED' from pytest summary must NOT trigger gate 1."""
        events = [_make_event("prompt_classified", reason="5 passed, 0 FAILED")]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome != "failed"

    def test_gate_1_takes_priority_over_completion(self) -> None:
        """Error + completion markers → still fails (gate 1 before gate 2)."""
        events = [
            _make_event("prompt_classified", reason="completed successfully"),
            _make_event("prompt_classified", reason="Traceback (most recent)"),
        ]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome == "failed"

    def test_gate_2_success_on_completion_markers(self) -> None:
        """Original stub: work done + 'done' marker → 'success'."""
        events = [
            _make_event("file_edited", file_path="a.py", language="python",
                        timestamp="2026-04-14T10:00:00+00:00"),
            _make_event("prompt_classified", reason="task done",
                        timestamp="2026-04-14T10:00:30+00:00"),
        ]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome == "success"

    def test_gate_2_requires_work_done(self) -> None:
        """Completion marker but no file_edited/prompt_classified → not success."""
        events = [_make_event("shell_guard", decision="allow", reason="done")]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome != "success"

    def test_gate_2_requires_completion_marker(self) -> None:
        """Work done but no completion marker → not success.

        Use status='ok' so the word 'completed' doesn't sneak into the corpus
        via the status string and trigger the completion check.
        """
        events = [
            _make_event("file_edited", file_path="a.py", language="python",
                        timestamp="2026-04-14T10:00:00+00:00"),
            _make_event("file_edited", file_path="b.py", language="python",
                        timestamp="2026-04-14T10:02:00+00:00"),
        ]
        outcome, _ = _mod.derive_session_outcome("ok", events)
        assert outcome != "success"

    def test_gate_2_success_with_finished_marker(self) -> None:
        events = [
            _make_event("prompt_classified", reason="finished the task",
                        timestamp="2026-04-14T10:00:00+00:00"),
        ]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome == "success"

    def test_gate_3_abandoned_on_short_session(self) -> None:
        """Original stub: no completion + duration < 60s → 'abandoned'."""
        events = [
            _make_event("file_edited", file_path="x.py", language="python",
                        timestamp="2026-04-14T10:00:00+00:00"),
            _make_event("file_edited", file_path="y.py", language="python",
                        timestamp="2026-04-14T10:00:10+00:00"),
        ]
        # status='ok' keeps the completion-marker check clean
        outcome, _ = _mod.derive_session_outcome("ok", events)
        assert outcome == "abandoned"

    def test_gate_3_not_abandoned_on_long_session(self) -> None:
        """Duration >= 60s without completion markers → 'unknown', not 'abandoned'."""
        events = [
            _make_event("shell_guard", decision="allow",
                        timestamp="2026-04-14T10:00:00+00:00"),
            _make_event("shell_guard", decision="allow",
                        timestamp="2026-04-14T10:05:00+00:00"),
        ]
        outcome, _ = _mod.derive_session_outcome("ok", events)
        assert outcome == "unknown"

    def test_gate_4_unknown_on_ambiguous_signals(self) -> None:
        """Original stub: long session, no completion, no errors → 'unknown'."""
        events = [
            _make_event("shell_guard", decision="allow",
                        timestamp="2026-04-14T10:00:00+00:00"),
            _make_event("shell_guard", decision="allow",
                        timestamp="2026-04-14T10:02:00+00:00"),
        ]
        outcome, _ = _mod.derive_session_outcome("completed", events)
        assert outcome == "unknown"

    def test_empty_events_and_ok_status_is_abandoned(self) -> None:
        """No events → duration=0 < 60s → abandoned (status='ok' avoids
        the completion-marker false-positive from 'completed')."""
        outcome, _ = _mod.derive_session_outcome("ok", [])
        assert outcome == "abandoned"

    def test_outcome_reason_non_empty(self) -> None:
        _, reason = _mod.derive_session_outcome("failed", [])
        assert reason


# ---------------------------------------------------------------------------
# Session aggregation — patches EVENTS_LOG
# ---------------------------------------------------------------------------


class TestSessionAggregation:
    def test_mixed_events_aggregated_correctly(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: prompts, edits, and shell events all counted."""
        log = tmp_path / "events.jsonl"
        _write_events(log, [
            _make_event("prompt_classified"),
            _make_event("prompt_classified"),
            _make_event("file_edited", file_path="a.py", language="python"),
            _make_event("file_edited", file_path="b.ts", language="typescript"),
            _make_event("shell_guard", decision="allow"),
            _make_event("shell_guard", decision="deny"),
            _make_event("shell_guard", decision="warn"),
        ])
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "completed")
        assert result["prompts_classified"] == 2
        assert result["files_edited"] == 2
        assert result["shell_commands"]["allowed"] == 1
        assert result["shell_commands"]["denied"] == 1
        assert result["shell_commands"]["warned"] == 1

    def test_empty_events_file_produces_zero_counts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: empty log → all counts zero."""
        log = tmp_path / "events.jsonl"
        log.write_text("")
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "completed")
        assert result["prompts_classified"] == 0
        assert result["files_edited"] == 0
        assert result["shell_commands"] == {"allowed": 0, "denied": 0, "warned": 0}

    def test_missing_events_file_does_not_crash(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: absent events.jsonl → returns zero-count summary."""
        monkeypatch.setattr(_mod, "EVENTS_LOG", tmp_path / "nonexistent.jsonl")
        result = _mod.aggregate_session("c-001", "completed")
        assert result["prompts_classified"] == 0

    def test_only_matching_conversation_counted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: events from other conversations are ignored."""
        log = tmp_path / "events.jsonl"
        _write_events(log, [
            _make_event("prompt_classified", conversation_id="c-001"),
            _make_event("prompt_classified", conversation_id="c-002"),
            _make_event("file_edited", conversation_id="c-002", file_path="x.py", language="python"),
        ])
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "completed")
        assert result["prompts_classified"] == 1
        assert result["files_edited"] == 0

    def test_malformed_lines_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: malformed JSON lines are silently skipped."""
        log = tmp_path / "events.jsonl"
        log.write_text(
            json.dumps(_make_event("prompt_classified")) + "\n"
            + "THIS IS NOT JSON\n"
            + "{broken\n"
            + json.dumps(_make_event("prompt_classified")) + "\n"
        )
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "completed")
        assert result["prompts_classified"] == 2

    def test_language_other_excluded_from_summary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: language='other' is not included in the languages list."""
        log = tmp_path / "events.jsonl"
        _write_events(log, [
            _make_event("file_edited", file_path="Makefile", language="other"),
            _make_event("file_edited", file_path="app.py", language="python"),
        ])
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "completed")
        assert "other" not in result["languages"]
        assert "python" in result["languages"]

    def test_status_passed_through_to_summary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Original stub: raw status string appears in summary."""
        log = tmp_path / "events.jsonl"
        log.write_text("")
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "my-custom-status")
        assert result["session_status"] == "my-custom-status"

    def test_duplicate_file_paths_deduplicated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same file edited twice counts as 1 unique file."""
        log = tmp_path / "events.jsonl"
        _write_events(log, [
            _make_event("file_edited", file_path="a.py", language="python"),
            _make_event("file_edited", file_path="a.py", language="python"),
        ])
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "completed")
        assert result["files_edited"] == 1

    def test_languages_sorted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "events.jsonl"
        _write_events(log, [
            _make_event("file_edited", file_path="a.ts", language="typescript"),
            _make_event("file_edited", file_path="b.py", language="python"),
            _make_event("file_edited", file_path="c.js", language="javascript"),
        ])
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "completed")
        assert result["languages"] == sorted(result["languages"])

    def test_summary_contains_conversation_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "events.jsonl"
        log.write_text("")
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("my-conv-id", "completed")
        assert result["conversation_id"] == "my-conv-id"

    def test_summary_contains_outcome(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "events.jsonl"
        log.write_text("")
        monkeypatch.setattr(_mod, "EVENTS_LOG", log)
        result = _mod.aggregate_session("c-001", "failed")
        assert result["session_outcome"] == "failed"


# ---------------------------------------------------------------------------
# Session summary persistence
# ---------------------------------------------------------------------------


class TestSessionSummaryPersistence:
    def test_session_summary_written_to_sessions_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Original stub: summary JSON is written to sessions/<id>.json."""
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
        monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
        summary = {"conversation_id": "c-001", "session_outcome": "success"}
        _mod._write_session_summary("c-001", summary)
        written = sessions / "c-001.json"
        assert written.is_file()
        data = json.loads(written.read_text())
        assert data["session_outcome"] == "success"

    def test_summary_merge_preserves_ci_passing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
        monkeypatch.setattr(_lib_common, "SESSIONS_DIR", sessions)
        monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
        pre = sessions / "c-001.json"
        pre.write_text(json.dumps({"ci_passing": True, "started_at": "2026-01-01"}))
        summary = {"conversation_id": "c-001", "session_outcome": "success"}
        _mod._write_session_summary("c-001", summary)
        data = json.loads((sessions / "c-001.json").read_text())
        assert data["session_outcome"] == "success"
        assert data["ci_passing"] is True
        assert data["started_at"] == "2026-01-01"

    def test_empty_conversation_id_skips_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() must not write a file when conversation_id is empty."""
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
        monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
        monkeypatch.setattr(_mod, "EVENTS_LOG", tmp_path / "events.jsonl")
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"conversation_id": "", "status": "completed"})
        _stub_stop_emit_and_pattern_sync(monkeypatch)
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        assert list(sessions.iterdir()) == []

    def test_summary_file_is_valid_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
        monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
        _mod._write_session_summary("c-999", {"x": 1, "y": [1, 2]})
        data = json.loads((sessions / "c-999.json").read_text())
        assert data == {"x": 1, "y": [1, 2]}


# ---------------------------------------------------------------------------
# Correlation threading
# ---------------------------------------------------------------------------


class TestCorrelationThreading:
    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        conv: str = "c-001",
        status: str = "completed",
        session: Dict = {},
    ) -> Dict:
        events_out: List[Dict] = []
        monkeypatch.setattr(_mod, "read_session_context", lambda: session)
        monkeypatch.setattr(_mod, "log_event", lambda e: events_out.append(e))
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"conversation_id": conv, "status": status})
        monkeypatch.setattr(_mod, "_load_events", lambda cid: [])
        monkeypatch.setattr(_mod, "_write_session_summary", lambda cid, s: None)
        _stub_stop_emit_and_pattern_sync(monkeypatch)
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        return events_out[0]

    def test_correlation_id_from_session_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, session={"latest_correlation_id": "abc123def456"})
        assert e["correlation_id"] == "abc123def456"

    def test_missing_session_uses_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, session={})
        assert e["correlation_id"] == ""

    def test_extra_session_fields_do_not_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, session={
            "latest_correlation_id": "valid0000001",
            "conversation_id": "c-001",
            "started_at": "2026-04-14T00:00:00+00:00",
        })
        assert e["correlation_id"] == "valid0000001"

    def test_correlation_id_on_failed_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(
            monkeypatch,
            status="failed",
            session={"latest_correlation_id": "failcorr0001"},
        )
        assert e["correlation_id"] == "failcorr0001"
        assert e["session_outcome"] == "failed"


# ---------------------------------------------------------------------------
# Typed event schema
# ---------------------------------------------------------------------------


class TestTypedEventSchema:
    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        conv: str = "s-001",
        status: str = "completed",
    ) -> Dict:
        events_out: List[Dict] = []
        monkeypatch.setattr(_mod, "read_session_context", lambda: {"latest_correlation_id": "test000abc12"})
        monkeypatch.setattr(_mod, "log_event", lambda e: events_out.append(e))
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"conversation_id": conv, "status": status})
        monkeypatch.setattr(_mod, "_load_events", lambda cid: [])
        monkeypatch.setattr(_mod, "_write_session_summary", lambda cid, s: None)
        _stub_stop_emit_and_pattern_sync(monkeypatch)
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        return events_out[0]

    def test_event_type_is_session_stopped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["event"] == "session_stopped"

    def test_event_has_conversation_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["conversation_id"] == "s-001"

    def test_event_has_correlation_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["correlation_id"] == "test000abc12"

    def test_event_has_session_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["session_status"] == "completed"

    def test_event_has_session_outcome(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert "session_outcome" in self._run(monkeypatch)

    def test_event_has_session_outcome_reason(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert "session_outcome_reason" in self._run(monkeypatch)

    def test_event_has_hook_duration_ms(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch)
        assert "hook_duration_ms" in e and isinstance(e["hook_duration_ms"], int)

    def test_event_has_summary_block(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch)
        assert "summary" in e and isinstance(e["summary"], dict)

    def test_stdout_is_empty_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"conversation_id": "c-1", "status": "completed"})
        monkeypatch.setattr(_mod, "_load_events", lambda cid: [])
        monkeypatch.setattr(_mod, "_write_session_summary", lambda cid, s: None)
        _stub_stop_emit_and_pattern_sync(monkeypatch)
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        _mod.main()
        assert json.loads(buf.getvalue().strip()) == {}

    def test_event_logged_exactly_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        events_out: List[Dict] = []
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda e: events_out.append(e))
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"conversation_id": "c-1", "status": "completed"})
        monkeypatch.setattr(_mod, "_load_events", lambda cid: [])
        monkeypatch.setattr(_mod, "_write_session_summary", lambda cid, s: None)
        _stub_stop_emit_and_pattern_sync(monkeypatch)
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        assert len(events_out) == 1

    def test_failed_status_reflected_in_event(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, status="failed")
        assert e["session_outcome"] == "failed"


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


class TestRobustness:
    def test_exception_in_main_does_not_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_mod, "read_stdin", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        _mod.main()
        assert json.loads(buf.getvalue().strip()) == {}

    def test_stdout_always_empty_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Even on success, stdout must be {} (informational hook)."""
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"conversation_id": "c-1", "status": "completed"})
        monkeypatch.setattr(_mod, "_load_events", lambda cid: [])
        monkeypatch.setattr(_mod, "_write_session_summary", lambda cid, s: None)
        _stub_stop_emit_and_pattern_sync(monkeypatch)
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        _mod.main()
        assert json.loads(buf.getvalue().strip()) == {}


class TestRecapFile:
    def test_last_recap_written_on_stop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        recap_path = tmp_path / "last-recap.md"
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"conversation_id": "test-conv", "status": "success"})
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "_load_events", lambda cid: [])
        monkeypatch.setattr(_mod, "_write_session_summary", lambda cid, s: None)
        monkeypatch.setattr(_mod, "log_event", lambda e: None)
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        _stub_stop_emit_and_pattern_sync(monkeypatch)
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        _mod.main()
        assert recap_path.exists()
        assert "Session Recap" in recap_path.read_text()

    def test_last_recap_contains_outcome(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        recap_path = tmp_path / "last-recap.md"
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"conversation_id": "test-conv", "status": "failed"})
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "_load_events", lambda cid: [])
        monkeypatch.setattr(_mod, "_write_session_summary", lambda cid, s: None)
        monkeypatch.setattr(_mod, "log_event", lambda e: None)
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        _stub_stop_emit_and_pattern_sync(monkeypatch)
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        _mod.main()
        assert "failed" in recap_path.read_text()

"""Tests for .cursor/hooks/on_stop.py — session aggregation."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".cursor" / "hooks"))

import _common
from on_stop import aggregate_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_events(events_log: Path, events: list) -> None:
    """Write a list of event dicts to an events.jsonl file."""
    events_log.parent.mkdir(parents=True, exist_ok=True)
    with events_log.open("w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt) + "\n")


# ---------------------------------------------------------------------------
# aggregate_session
# ---------------------------------------------------------------------------


class TestAggregateSession:
    def test_mixed_event_types(self, tmp_path, monkeypatch):
        events_log = tmp_path / "events.jsonl"
        monkeypatch.setattr(_common, "EVENTS_LOG", events_log)

        _write_events(
            events_log,
            [
                {"event": "prompt_classified", "conversation_id": "sess-A", "matched_agent": "debug-intelligence"},
                {"event": "prompt_classified", "conversation_id": "sess-A", "matched_agent": "testing"},
                {"event": "file_edited", "conversation_id": "sess-A", "file_path": "src/a.py", "language": "python"},
                {"event": "file_edited", "conversation_id": "sess-A", "file_path": "src/b.ts", "language": "typescript"},
                {"event": "file_edited", "conversation_id": "sess-A", "file_path": "src/a.py", "language": "python"},
                {"event": "shell_guard", "conversation_id": "sess-A", "decision": "allow"},
                {"event": "shell_guard", "conversation_id": "sess-A", "decision": "allow"},
                {"event": "shell_guard", "conversation_id": "sess-A", "decision": "deny"},
                {"event": "shell_guard", "conversation_id": "sess-A", "decision": "warn"},
            ],
        )

        summary = aggregate_session("sess-A", "completed")

        assert summary["conversation_id"] == "sess-A"
        assert summary["session_status"] == "completed"
        assert summary["prompts_classified"] == 2
        assert summary["files_edited"] == 2  # unique paths: a.py, b.ts
        assert summary["shell_commands"] == {"allowed": 2, "denied": 1, "warned": 1}
        assert sorted(summary["languages"]) == ["python", "typescript"]

    def test_empty_events_file(self, tmp_path, monkeypatch):
        events_log = tmp_path / "events.jsonl"
        events_log.write_text("")
        monkeypatch.setattr(_common, "EVENTS_LOG", events_log)

        summary = aggregate_session("sess-empty", "completed")

        assert summary["prompts_classified"] == 0
        assert summary["files_edited"] == 0
        assert summary["shell_commands"] == {"allowed": 0, "denied": 0, "warned": 0}
        assert summary["languages"] == []

    def test_missing_events_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_common, "EVENTS_LOG", tmp_path / "nonexistent.jsonl")

        summary = aggregate_session("sess-missing", "aborted")

        assert summary["prompts_classified"] == 0
        assert summary["files_edited"] == 0
        assert summary["session_status"] == "aborted"

    def test_only_matching_conversation_counted(self, tmp_path, monkeypatch):
        events_log = tmp_path / "events.jsonl"
        monkeypatch.setattr(_common, "EVENTS_LOG", events_log)

        _write_events(
            events_log,
            [
                {"event": "prompt_classified", "conversation_id": "sess-1"},
                {"event": "prompt_classified", "conversation_id": "sess-2"},
                {"event": "prompt_classified", "conversation_id": "sess-1"},
                {"event": "file_edited", "conversation_id": "sess-2", "file_path": "x.py", "language": "python"},
                {"event": "shell_guard", "conversation_id": "sess-1", "decision": "deny"},
                {"event": "shell_guard", "conversation_id": "sess-2", "decision": "allow"},
            ],
        )

        summary_1 = aggregate_session("sess-1", "completed")
        assert summary_1["prompts_classified"] == 2
        assert summary_1["files_edited"] == 0
        assert summary_1["shell_commands"]["denied"] == 1
        assert summary_1["shell_commands"]["allowed"] == 0

        summary_2 = aggregate_session("sess-2", "completed")
        assert summary_2["prompts_classified"] == 1
        assert summary_2["files_edited"] == 1
        assert summary_2["shell_commands"]["allowed"] == 1
        assert summary_2["shell_commands"]["denied"] == 0

    def test_malformed_lines_skipped(self, tmp_path, monkeypatch):
        events_log = tmp_path / "events.jsonl"
        monkeypatch.setattr(_common, "EVENTS_LOG", events_log)

        events_log.write_text(
            '{"event": "prompt_classified", "conversation_id": "s1"}\n'
            "not json at all\n"
            "\n"
            '{"event": "shell_guard", "conversation_id": "s1", "decision": "allow"}\n'
        )

        summary = aggregate_session("s1", "completed")
        assert summary["prompts_classified"] == 1
        assert summary["shell_commands"]["allowed"] == 1

    def test_language_other_excluded(self, tmp_path, monkeypatch):
        events_log = tmp_path / "events.jsonl"
        monkeypatch.setattr(_common, "EVENTS_LOG", events_log)

        _write_events(
            events_log,
            [
                {"event": "file_edited", "conversation_id": "s1", "file_path": "Makefile", "language": "other"},
                {"event": "file_edited", "conversation_id": "s1", "file_path": "x.py", "language": "python"},
            ],
        )

        summary = aggregate_session("s1", "completed")
        assert summary["languages"] == ["python"]  # "other" excluded

    def test_status_passthrough(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_common, "EVENTS_LOG", tmp_path / "empty.jsonl")
        (tmp_path / "empty.jsonl").write_text("")

        for status in ["completed", "aborted", "error"]:
            summary = aggregate_session("s", status)
            assert summary["session_status"] == status

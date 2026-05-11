"""Tests for src/omnicursor/session_outbox.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from omnicursor.session_outbox import write_session_outcome


def _payload(**extra: object) -> dict:
    base: dict = {
        "schema_version": "omnicursor.session_outcome.v1",
        "source": "omnicursor",
        "correlation_id": "corr-123",
        "conversation_id": "conv-abc",
        "started_at": "2026-05-09T10:00:00Z",
        "ended_at": "2026-05-09T10:05:00Z",
        "session_status": "stopped",
        "session_outcome": "success",
        "session_outcome_reason": "completion markers found",
        "prompts_classified": 2,
        "files_edited": 3,
        "shell_commands": {"allowed": 1, "denied": 0, "warned": 0},
        "languages": ["python"],
        "matched_agent": "debugging",
        "matched_confidence": 0.95,
        "patterns_injected": 5,
        "injected_pattern_ids": ["auto-abc123", "auto-def456"],
    }
    base.update(extra)
    return base


class TestWriteSessionOutcome:
    def test_creates_file_on_first_write(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        assert write_session_outcome(_payload(), outbox_path=outbox) is True
        assert outbox.exists()

    def test_written_line_is_valid_json(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        write_session_outcome(_payload(), outbox_path=outbox)
        lines = outbox.read_text().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["schema_version"] == "omnicursor.session_outcome.v1"
        assert data["source"] == "omnicursor"

    def test_append_does_not_destroy_previous_line(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        write_session_outcome(_payload(conversation_id="conv-1"), outbox_path=outbox)
        write_session_outcome(_payload(conversation_id="conv-2"), outbox_path=outbox)
        lines = outbox.read_text().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["conversation_id"] == "conv-1"
        assert json.loads(lines[1])["conversation_id"] == "conv-2"

    def test_each_line_independently_parseable(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        for i in range(5):
            write_session_outcome(_payload(conversation_id=f"conv-{i}"), outbox_path=outbox)
        for line in outbox.read_text().splitlines():
            data = json.loads(line)
            assert "conversation_id" in data

    def test_env_override_respected(self, tmp_path: Path, monkeypatch: mock.MagicMock) -> None:
        outbox = tmp_path / "custom_outbox.jsonl"
        monkeypatch.setenv("OMNICURSOR_OUTBOX_FILE", str(outbox))
        write_session_outcome(_payload())
        assert outbox.exists()

    def test_explicit_path_takes_precedence_over_env(
        self, tmp_path: Path, monkeypatch: mock.MagicMock
    ) -> None:
        env_outbox = tmp_path / "env_outbox.jsonl"
        explicit_outbox = tmp_path / "explicit_outbox.jsonl"
        monkeypatch.setenv("OMNICURSOR_OUTBOX_FILE", str(env_outbox))
        write_session_outcome(_payload(), outbox_path=explicit_outbox)
        assert explicit_outbox.exists()
        assert not env_outbox.exists()

    def test_returns_false_on_io_error(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        with mock.patch("builtins.open", side_effect=OSError("disk full")):
            result = write_session_outcome(_payload(), outbox_path=outbox)
        assert result is False

    def test_io_error_does_not_raise(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        with mock.patch("builtins.open", side_effect=OSError("disk full")):
            write_session_outcome(_payload(), outbox_path=outbox)  # must not raise

    def test_non_ascii_payload_written_correctly(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        write_session_outcome(
            _payload(session_outcome_reason="patrón aprendido con éxito"),
            outbox_path=outbox,
        )
        line = outbox.read_text(encoding="utf-8").strip()
        data = json.loads(line)
        assert "patrón" in data["session_outcome_reason"]

    def test_all_outcome_types_written(self, tmp_path: Path) -> None:
        for outcome in ("success", "failed", "abandoned", "unknown"):
            outbox = tmp_path / f"{outcome}.jsonl"
            assert write_session_outcome(_payload(session_outcome=outcome), outbox_path=outbox) is True
            data = json.loads(outbox.read_text().strip())
            assert data["session_outcome"] == outcome

    def test_injected_pattern_ids_preserved(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        ids = ["auto-aaa", "auto-bbb", "auto-ccc"]
        write_session_outcome(_payload(injected_pattern_ids=ids), outbox_path=outbox)
        data = json.loads(outbox.read_text().strip())
        assert data["injected_pattern_ids"] == ids

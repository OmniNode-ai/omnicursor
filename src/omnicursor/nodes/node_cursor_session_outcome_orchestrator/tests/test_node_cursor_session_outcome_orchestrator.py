# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.input import (
    SessionOutcomeInput,
)
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.output import (
    SessionOutcomeOutput,
)
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.handlers.handle_session_stop import (
    handle_session_stop,
)
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.node import run
from omnicursor.session_outcome import format_recap


class TestSessionOutcomeModels:
    def test_input_requires_status(self):
        with pytest.raises(Exception):
            SessionOutcomeInput()

    def test_input_events_defaults_empty(self):
        i = SessionOutcomeInput(status="success")
        assert i.events == []

    def test_output_has_outcome_and_reason(self):
        o = SessionOutcomeOutput(outcome="success", reason="work done")
        assert o.outcome == "success"


class TestHandlerSessionStop:
    def test_failed_status_returns_failed(self):
        result = handle_session_stop(SessionOutcomeInput(status="failed"))
        assert result.outcome == "failed"

    def test_error_status_returns_failed(self):
        result = handle_session_stop(SessionOutcomeInput(status="error"))
        assert result.outcome == "failed"

    def test_short_session_no_work_returns_abandoned(self):
        result = handle_session_stop(SessionOutcomeInput(status="stopped", events=[]))
        assert result.outcome in {"abandoned", "unknown"}

    def test_success_with_work_done(self):
        events = [
            {"event": "file_edited", "timestamp": "2026-01-01T00:00:00"},
            {"event": "prompt_classified", "timestamp": "2026-01-01T00:01:00"},
            {"text": "Task completed successfully", "timestamp": "2026-01-01T00:02:00"},
        ]
        result = handle_session_stop(
            SessionOutcomeInput(status="success", events=events)
        )
        assert result.outcome in {"success", "unknown"}

    def test_output_is_typed(self):
        result = handle_session_stop(SessionOutcomeInput(status="stopped"))
        assert isinstance(result, SessionOutcomeOutput)

    def test_reason_is_non_empty(self):
        result = handle_session_stop(SessionOutcomeInput(status="failed"))
        assert len(result.reason) > 0

    def test_outcome_is_valid_value(self):
        result = handle_session_stop(SessionOutcomeInput(status="stopped"))
        assert result.outcome in {"success", "failed", "abandoned", "unknown"}


class TestFormatRecap:
    def test_includes_outcome(self):
        summary = {
            "session_outcome": "success",
            "files_edited": 3,
            "shell_commands": {"allowed": 2, "warned": 0, "denied": 0},
            "prompts_classified": 4,
            "languages": ["python"],
        }
        text = format_recap(summary)
        assert "success" in text

    def test_includes_files_edited(self):
        summary = {
            "session_outcome": "unknown",
            "files_edited": 5,
            "shell_commands": {"allowed": 1, "warned": 0, "denied": 0},
            "prompts_classified": 2,
            "languages": [],
        }
        text = format_recap(summary)
        assert "5" in text

    def test_includes_section_header(self):
        summary = {
            "session_outcome": "abandoned",
            "files_edited": 0,
            "shell_commands": {"allowed": 0, "warned": 0, "denied": 0},
            "prompts_classified": 0,
            "languages": [],
        }
        text = format_recap(summary)
        assert "Session Recap" in text

    def test_empty_languages_renders_cleanly(self):
        summary = {
            "session_outcome": "failed",
            "files_edited": 0,
            "shell_commands": {"allowed": 0, "warned": 0, "denied": 1},
            "prompts_classified": 0,
            "languages": [],
        }
        text = format_recap(summary)
        assert "Session Recap" in text


class TestNodeRunAPI:
    def test_run_returns_output(self):
        result = run("stopped")
        assert isinstance(result, SessionOutcomeOutput)

    def test_run_failed_status(self):
        result = run("failed")
        assert result.outcome == "failed"

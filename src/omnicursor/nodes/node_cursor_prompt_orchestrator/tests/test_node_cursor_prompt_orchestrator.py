# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Tests for node_cursor_prompt_orchestrator.

Exercises the full handler path via the node.run() API. No Cursor
environment required — handler loads agent_scoring.py via importlib.
"""

from __future__ import annotations

import pytest

from omnicursor.nodes.node_cursor_prompt_orchestrator.models.input import (
    PromptOrchestratorInput,
)
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.output import (
    PromptOrchestratorOutput,
)
from omnicursor.nodes.node_cursor_prompt_orchestrator.handlers.handle_prompt_submitted import (
    handle_prompt_submitted,
)
from omnicursor.nodes.node_cursor_prompt_orchestrator.node import run


class TestPromptOrchestratorModels:
    def test_input_requires_prompt(self):
        with pytest.raises(Exception):
            PromptOrchestratorInput()

    def test_input_optional_fields_default_none(self):
        i = PromptOrchestratorInput(prompt="test")
        assert i.session_id is None
        assert i.context is None

    def test_output_has_required_fields(self):
        o = PromptOrchestratorOutput(
            agent_name="debugging",
            confidence=0.95,
            reason="Exact trigger",
            system_message="<!-- OmniCursor Agent: debugging (0.95) -->",
        )
        assert o.patterns_injected == []


class TestHandlerRouting:
    def test_debug_prompt_routes_to_debug_agent(self):
        result = handle_prompt_submitted(
            PromptOrchestratorInput(prompt="I have a bug in my code")
        )
        assert "debug" in result.agent_name
        assert result.confidence >= 0.55

    def test_brainstorm_prompt_routes_to_brainstorm_agent(self):
        result = handle_prompt_submitted(
            PromptOrchestratorInput(prompt="let's brainstorm a new feature")
        )
        assert "brainstorm" in result.agent_name
        assert result.confidence >= 0.55

    def test_unknown_prompt_returns_polymorphic_fallback(self):
        result = handle_prompt_submitted(
            PromptOrchestratorInput(prompt="xyzzy nonsense gibberish")
        )
        assert result.agent_name == "polymorphic-agent"
        assert result.confidence == 0.0

    def test_output_is_typed(self):
        result = handle_prompt_submitted(
            PromptOrchestratorInput(prompt="debug this error")
        )
        assert isinstance(result, PromptOrchestratorOutput)

    def test_system_message_format(self):
        result = handle_prompt_submitted(PromptOrchestratorInput(prompt="I have a bug"))
        assert result.system_message.startswith("<!-- OmniCursor Agent:")
        assert result.system_message.endswith("-->")

    def test_confidence_within_bounds(self):
        result = handle_prompt_submitted(PromptOrchestratorInput(prompt="fix this bug"))
        assert 0.0 <= result.confidence <= 1.0

    def test_patterns_injected_defaults_empty(self):
        result = handle_prompt_submitted(PromptOrchestratorInput(prompt="debug"))
        assert result.patterns_injected == []


class TestNodeRunAPI:
    def test_run_returns_output(self):
        result = run("I have a bug")
        assert isinstance(result, PromptOrchestratorOutput)

    def test_run_accepts_session_id(self):
        result = run("debug this", session_id="test-session-123")
        assert isinstance(result, PromptOrchestratorOutput)

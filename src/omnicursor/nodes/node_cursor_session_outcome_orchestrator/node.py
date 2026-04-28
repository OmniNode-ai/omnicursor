# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from omnicursor.nodes.node_cursor_session_outcome_orchestrator.handlers.handle_session_stop import handle_session_stop
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.input import SessionOutcomeInput
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.output import SessionOutcomeOutput

CONTRACT_NAME = "node_cursor_session_outcome_orchestrator"


def run(status: str, events: list[dict] | None = None) -> SessionOutcomeOutput:
    return handle_session_stop(SessionOutcomeInput(status=status, events=events or []))

# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.input import SessionOutcomeInput
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.output import SessionOutcomeOutput
from omnicursor.session_outcome import derive_session_outcome


def handle_session_stop(input: SessionOutcomeInput) -> SessionOutcomeOutput:
    outcome, reason = derive_session_outcome(input.status, input.events)
    return SessionOutcomeOutput(outcome=outcome, reason=reason)

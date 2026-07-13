# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""node_cursor_prompt_orchestrator — thin dispatch shell.

Runtime execution is .cursor/hooks/scripts/user-prompt-submit.py (stdlib only).
This module is the library surface: validates input, calls the handler, returns
typed output. Use for tests, CI, and optional scripting.
"""

from __future__ import annotations

from omnicursor.nodes.node_cursor_prompt_orchestrator.handlers.handle_prompt_submitted import (
    handle_prompt_submitted,
)
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.input import (
    PromptOrchestratorInput,
)
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.output import (
    PromptOrchestratorOutput,
)

CONTRACT_NAME = "node_cursor_prompt_orchestrator"


def run(prompt: str, session_id: str | None = None) -> PromptOrchestratorOutput:
    """Classify a prompt and return a typed routing result."""
    input_ = PromptOrchestratorInput(prompt=prompt, session_id=session_id)
    return handle_prompt_submitted(input_)

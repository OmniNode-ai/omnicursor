# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from omnicursor.agents import _ALL_RAW_AGENTS
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.input import (
    PromptOrchestratorInput,
)
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.output import (
    PromptOrchestratorOutput,
)
from omnicursor.scoring import HARD_FLOOR, extract_keywords, score_agent


def handle_prompt_submitted(input: PromptOrchestratorInput) -> PromptOrchestratorOutput:
    prompt_lower = input.prompt.lower()
    prompt_words: set[str] = set(extract_keywords(input.prompt))

    best_name = "polymorphic-agent"
    best_score = 0.0
    best_reason = "No agent matched"

    for agent in _ALL_RAW_AGENTS:
        name = agent.get("name", "")
        if not name:
            continue
        sc, reason = score_agent(prompt_lower, prompt_words, agent)
        if sc >= HARD_FLOOR and sc > best_score:
            best_score, best_name, best_reason = sc, name, reason

    system_message = f"<!-- OmniCursor Agent: {best_name} ({best_score:.2f}) -->"

    return PromptOrchestratorOutput(
        agent_name=best_name,
        confidence=best_score,
        reason=best_reason,
        system_message=system_message,
        patterns_injected=[],
    )

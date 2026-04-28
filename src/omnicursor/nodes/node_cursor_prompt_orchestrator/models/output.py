# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pydantic import BaseModel


class PromptOrchestratorOutput(BaseModel):
    agent_name: str
    confidence: float
    reason: str
    system_message: str
    patterns_injected: list[str] = []

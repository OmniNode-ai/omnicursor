# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pydantic import BaseModel


class PromptOrchestratorInput(BaseModel):
    prompt: str
    session_id: str | None = None
    context: dict | None = None

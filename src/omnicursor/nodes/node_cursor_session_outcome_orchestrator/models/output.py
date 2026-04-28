# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pydantic import BaseModel


class SessionOutcomeOutput(BaseModel):
    outcome: str  # "success" | "failed" | "abandoned" | "unknown"
    reason: str

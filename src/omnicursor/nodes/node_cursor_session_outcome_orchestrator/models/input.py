# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pydantic import BaseModel


class SessionOutcomeInput(BaseModel):
    status: str
    events: list[dict] = []

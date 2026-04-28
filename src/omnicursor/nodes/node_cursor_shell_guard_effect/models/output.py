# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pydantic import BaseModel


class ShellGuardOutput(BaseModel):
    permission: str  # "allow" | "deny"
    user_message: str | None = None

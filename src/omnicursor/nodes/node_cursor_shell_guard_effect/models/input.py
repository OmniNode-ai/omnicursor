# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pydantic import BaseModel


class ShellGuardInput(BaseModel):
    command: str
    conversation_id: str = ""

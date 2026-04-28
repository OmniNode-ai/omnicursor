# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class PatternInjectionInput(BaseModel):
    prompt: str
    patterns_file: Path
    domain: str = "general"

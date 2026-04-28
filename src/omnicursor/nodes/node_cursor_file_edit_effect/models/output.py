# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pydantic import BaseModel


class FileEditOutput(BaseModel):
    event: str
    file_path: str
    language: str
    edit_count: int
    ruff_findings: int
    conversation_id: str = ""

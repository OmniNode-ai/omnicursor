# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pydantic import BaseModel


class FileEditInput(BaseModel):
    file_path: str
    edits: list[dict] = []
    conversation_id: str = ""

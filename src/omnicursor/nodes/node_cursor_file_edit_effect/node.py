# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from omnicursor.nodes.node_cursor_file_edit_effect.handlers.handle_file_edited import handle_file_edited
from omnicursor.nodes.node_cursor_file_edit_effect.models.input import FileEditInput
from omnicursor.nodes.node_cursor_file_edit_effect.models.output import FileEditOutput

CONTRACT_NAME = "node_cursor_file_edit_effect"


def run(file_path: str, edits: list[dict] | None = None, conversation_id: str = "") -> FileEditOutput:
    return handle_file_edited(FileEditInput(
        file_path=file_path,
        edits=edits or [],
        conversation_id=conversation_id,
    ))

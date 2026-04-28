# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from omnicursor.file_edit import handle_edit
from omnicursor.nodes.node_cursor_file_edit_effect.models.input import FileEditInput
from omnicursor.nodes.node_cursor_file_edit_effect.models.output import FileEditOutput


def handle_file_edited(input: FileEditInput) -> FileEditOutput:
    result = handle_edit({
        "file_path": input.file_path,
        "edits": input.edits,
        "conversation_id": input.conversation_id,
    })
    return FileEditOutput(
        event=result["event"],
        file_path=result["file_path"],
        language=result["language"],
        edit_count=result["edit_count"],
        ruff_findings=result["ruff_findings"],
        conversation_id=result["conversation_id"],
    )

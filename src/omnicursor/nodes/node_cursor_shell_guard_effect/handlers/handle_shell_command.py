# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from omnicursor.nodes.node_cursor_shell_guard_effect.models.input import ShellGuardInput
from omnicursor.nodes.node_cursor_shell_guard_effect.models.output import ShellGuardOutput
from omnicursor.shell_guard import guard_command


def handle_shell_command(input: ShellGuardInput) -> ShellGuardOutput:
    result = guard_command(input.command, conversation_id=input.conversation_id)
    return ShellGuardOutput(
        permission=result["permission"],
        user_message=result.get("userMessage"),
    )

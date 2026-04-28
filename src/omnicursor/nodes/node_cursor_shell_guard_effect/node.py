# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from omnicursor.nodes.node_cursor_shell_guard_effect.handlers.handle_shell_command import handle_shell_command
from omnicursor.nodes.node_cursor_shell_guard_effect.models.input import ShellGuardInput
from omnicursor.nodes.node_cursor_shell_guard_effect.models.output import ShellGuardOutput

CONTRACT_NAME = "node_cursor_shell_guard_effect"


def run(command: str, conversation_id: str = "") -> ShellGuardOutput:
    return handle_shell_command(ShellGuardInput(command=command, conversation_id=conversation_id))

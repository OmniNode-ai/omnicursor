# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Library surface for ``node_cursor_shell_guard_effect``.

Runtime execution is ``hooks/scripts/shell-guard.py`` (stdlib only).
"""

from __future__ import annotations

CONTRACT_NAME = "node_cursor_shell_guard_effect"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "beforeShellExecution",
        "hooks_json_command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/shell-guard.py"',
        "implementation": "hooks/scripts/shell-guard.py",
        "blocking": True,
    }

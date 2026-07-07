# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Library surface for ``node_cursor_session_end_effect``.

Runtime execution is ``.cursor/hooks/scripts/session-end.py`` (stdlib only) —
emits the true conversation-close event under the ``session.ended`` registry
key, complementing ``stop`` (loop-end).
"""

from __future__ import annotations

CONTRACT_NAME = "node_cursor_session_end_effect"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "sessionEnd",
        "hooks_json_command": "python3 .cursor/hooks/scripts/session-end.py",
        "implementation": ".cursor/hooks/scripts/session-end.py",
        "blocking": False,
    }

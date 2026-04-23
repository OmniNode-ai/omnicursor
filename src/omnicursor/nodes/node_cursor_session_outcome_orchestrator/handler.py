# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Library surface for ``node_cursor_session_outcome_orchestrator``.

Runtime execution is ``.cursor/hooks/scripts/stop.py`` (stdlib only).
"""

from __future__ import annotations

CONTRACT_NAME = "node_cursor_session_outcome_orchestrator"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "stop",
        "hooks_json_command": "python3 .cursor/hooks/scripts/stop.py",
        "implementation": ".cursor/hooks/scripts/stop.py",
        "blocking": False,
    }

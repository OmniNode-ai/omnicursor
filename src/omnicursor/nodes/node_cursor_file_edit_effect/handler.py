# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Library surface for ``node_cursor_file_edit_effect``.

Runtime execution is ``.cursor/hooks/scripts/post-edit.py`` (stdlib only).
"""

from __future__ import annotations

CONTRACT_NAME = "node_cursor_file_edit_effect"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "afterFileEdit",
        "hooks_json_command": "python3 .cursor/hooks/scripts/post-edit.py",
        "implementation": ".cursor/hooks/scripts/post-edit.py",
        "blocking": False,
    }

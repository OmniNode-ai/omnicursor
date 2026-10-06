# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Library surface for ``node_cursor_tool_use_compute``.

Runtime execution is ``hooks/scripts/post-tool-use.py`` (stdlib only) —
the mid-session refresh channel: re-injects domain-relevant learned patterns via
``postToolUse.additional_context``. Context assembly is shared with the
sessionStart hook in ``hooks/lib/context_injection.py``.
"""

from __future__ import annotations

CONTRACT_NAME = "node_cursor_tool_use_compute"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "postToolUse",
        "hooks_json_command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-tool-use.py"',
        "implementation": "hooks/scripts/post-tool-use.py",
        "blocking": False,
    }

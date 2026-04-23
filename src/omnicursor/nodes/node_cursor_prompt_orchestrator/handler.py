# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Library surface for ``node_cursor_prompt_orchestrator``.

Runtime execution is ``.cursor/hooks/scripts/user-prompt-submit.py`` (stdlib only).
This module documents the binding for tests and tooling.
"""

from __future__ import annotations

CONTRACT_NAME = "node_cursor_prompt_orchestrator"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "beforeSubmitPrompt",
        "hooks_json_command": "python3 .cursor/hooks/scripts/user-prompt-submit.py",
        "implementation": ".cursor/hooks/scripts/user-prompt-submit.py",
        "blocking": False,
    }

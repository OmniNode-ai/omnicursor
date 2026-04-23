# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Read-side pattern selection — companion to ``beforeSubmitPrompt`` hook.

Canonical logic: ``.cursor/hooks/lib/prompt_pattern_selection.py`` (stdlib).
``omnicursor.prompt_pattern_read`` re-exports that module for this handler and
for tests. The hook imports the same file directly — see
``docs/dev/OMNICLAUDE_TO_CURSOR_PORT.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omnicursor.prompt_pattern_read import select_patterns_for_prompt

CONTRACT_NAME = "node_cursor_pattern_injection_compute"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "beforeSubmitPrompt",
        "hooks_json_command": "python3 .cursor/hooks/scripts/user-prompt-submit.py",
        "implementation": ".cursor/hooks/scripts/user-prompt-submit.py",
        "blocking": False,
    }


def read_patterns_for_prompt(
    patterns_file: Path,
    prompt: str,
    *,
    domain: str = "general",
) -> list[dict[str, Any]]:
    """Return ranked pattern dicts for ``prompt`` (read-only)."""
    return select_patterns_for_prompt(patterns_file, prompt=prompt, domain=domain)

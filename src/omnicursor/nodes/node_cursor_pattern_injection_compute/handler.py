# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Read-side pattern selection — companion to the ``sessionStart`` hook.

Context injection is session-level via ``sessionStart.additional_context`` (and
refreshed by ``postToolUse``); Cursor's ``beforeSubmitPrompt`` is block-only and
cannot inject. Canonical selection logic:
``hooks/lib/prompt_pattern_selection.py`` (stdlib); context assembly:
``hooks/lib/context_injection.py``. ``omnicursor.prompt_pattern_read``
re-exports the selection module for this handler and for tests — see
``docs/dev/OMNICLAUDE_TO_CURSOR_PORT.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omnicursor.prompt_pattern_read import select_patterns_for_prompt

CONTRACT_NAME = "node_cursor_pattern_injection_compute"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "sessionStart",
        "hooks_json_command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/session-start.py"',
        "implementation": "hooks/scripts/session-start.py",
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

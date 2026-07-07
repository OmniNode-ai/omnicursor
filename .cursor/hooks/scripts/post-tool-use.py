"""postToolUse hook — mid-session context refresh + tool-executed event.

Fires after a tool executes successfully. This is Cursor's second live injection
channel: it returns ``additional_context`` to refresh the model with learned
patterns relevant to the tool activity just observed (domain inferred from the
tool input's file path), keeping guidance current across a long session without
per-prompt injection (which Cursor does not support).

Also emits the ``tool.executed`` registry key for backend learning (the
registry YAML owns the topic string).

Node contract: ``node_cursor_tool_use_compute``
(``src/omnicursor/nodes/node_cursor_tool_use_compute/contract.yaml``). Stdlib
only; always exits 0; never blocks Cursor.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_hooks = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_hooks / "lib"))
sys.path.insert(0, str(_hooks.parent.parent / "src"))

from _common import (  # noqa: E402
    log_event,
    read_session_context,
    read_stdin,
    write_additional_context,
)
from context_injection import (  # noqa: E402
    build_refresh_context,
    fetch_patterns,
    infer_domain_from_path,
)
from emit_client import send_event  # noqa: E402


def _tool_file_path(tool_input: object) -> str:
    """Extract a file path from a tool_input object, if present."""
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "target_file"):
            val = tool_input.get(key)
            if isinstance(val, str) and val:
                return val
    return ""


def main() -> None:
    _start = time.monotonic()
    context_block = ""
    try:
        data = read_stdin()
        conversation_id = data.get("conversation_id", "")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})

        session = read_session_context()
        correlation_id = session.get("latest_correlation_id", "")

        domain = infer_domain_from_path(_tool_file_path(tool_input))
        patterns = fetch_patterns(domain)
        context_block = build_refresh_context(patterns=patterns, domain=domain)

        hook_ms = int((time.monotonic() - _start) * 1000)
        log_event(
            {
                "event": "tool_executed",
                "conversation_id": conversation_id,
                "correlation_id": correlation_id,
                "tool_name": tool_name,
                "domain": domain,
                "patterns_refreshed": len(patterns) if context_block else 0,
                "hook_duration_ms": hook_ms,
            }
        )

        send_event(
            "tool.executed",
            {
                "session_id": conversation_id,
                "correlation_id": correlation_id,
                "tool_name": tool_name,
                "domain": domain,
                "agent_source": "cursor",
            },
        )
    except Exception:
        pass

    write_additional_context(context_block)


if __name__ == "__main__":
    main()

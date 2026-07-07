"""afterFileEdit hook — post-edit diagnostics and event logging.

Node contract: ``node_cursor_file_edit_effect``
(``src/omnicursor/nodes/node_cursor_file_edit_effect/contract.yaml``).

Informational only — Cursor ignores stdout. Always exits cleanly.
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
    write_stdout,
)
from emit_client import send_event  # noqa: E402
from omnicursor.file_edit import detect_language, handle_edit, run_ruff_check, run_tsc_check  # noqa: E402, F401


def main() -> None:
    _start = time.monotonic()
    try:
        data = read_stdin()
        conversation_id = data.get("conversation_id", "")
        session = read_session_context()
        correlation_id: str = session.get("latest_correlation_id", "")

        result = handle_edit(data)
        hook_ms = int((time.monotonic() - _start) * 1000)

        log_event({
            **result,
            "correlation_id": correlation_id,
            "hook_duration_ms": hook_ms,
        })

        send_event(
            "tool.executed",
            {
                "session_id": conversation_id,
                "correlation_id": correlation_id,
                "tool_name": "edit_file",
                "file_path": result.get("file_path", ""),
                "language": result.get("language", ""),
                "agent_source": "cursor",
            },
        )
    except Exception:
        pass
    write_stdout({})


if __name__ == "__main__":
    main()

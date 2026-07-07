"""beforeShellExecution hook — two-tier shell command guard.

This hook CAN control execution. Returns deny to block, allow to proceed.

Node contract: ``node_cursor_shell_guard_effect``
(``src/omnicursor/nodes/node_cursor_shell_guard_effect/contract.yaml``).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

# Upper bound for denied-command audit logs (avoid multi-megabyte JSONL rows).
_MAX_DENIED_COMMAND_LOG_CHARS = 65536

_hooks = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_hooks / "lib"))
sys.path.insert(0, str(_hooks.parent.parent / "src"))

from _common import (  # noqa: E402
    SESSIONS_DIR,
    log_event,
    read_session_context,
    read_stdin,
    write_stdout,
)
from emit_client import send_event  # noqa: E402
from redaction import redact_secrets, sanitize_preview  # noqa: E402
from omnicursor.shell_guard import guard_command as _guard_command_impl  # noqa: E402

_DOD_CONFIG_PATH: Path = _hooks / "config" / "dod_enforcement.json"


def guard_command(command: str, *, conversation_id: str = "", sessions_root=None):
    """Hook-local wrapper that injects the DoD config path."""
    return _guard_command_impl(
        command,
        conversation_id=conversation_id,
        sessions_root=sessions_root,
        dod_config_path=_DOD_CONFIG_PATH,
    )


def main() -> None:
    _start = time.monotonic()
    try:
        data = read_stdin()
        command = data.get("command", "")
        conversation_id = data.get("conversation_id", "")

        session = read_session_context()
        correlation_id: str = session.get("latest_correlation_id", "")

        response = guard_command(command, conversation_id=conversation_id, sessions_root=SESSIONS_DIR)

        # Translate the guard result to Cursor's documented beforeShellExecution
        # output: {permission: allow|deny|ask, user_message, agent_message}. The
        # library returns camelCase (userMessage/agentMessage) which Cursor ignores,
        # so remap to snake_case at this boundary.
        permission = response.get("permission", "allow")
        user_message = response.get("user_message") or response.get("userMessage")
        agent_message = response.get("agent_message") or response.get("agentMessage")

        cursor_response: dict[str, Any] = {"permission": permission}
        if user_message:
            cursor_response["user_message"] = user_message
        if agent_message:
            cursor_response["agent_message"] = agent_message

        if permission == "deny":
            decision = "deny"
            reason = user_message or ""
        elif permission == "ask":
            decision = "ask"
            reason = user_message or agent_message or ""
        elif agent_message:
            decision = "warn"
            reason = agent_message
        else:
            decision = "allow"
            reason = ""

        hook_ms = int((time.monotonic() - _start) * 1000)

        # The audit log persists to disk (~/.omnicursor/events.jsonl) and
        # commands frequently carry tokens/URL creds — redact before logging
        # (A5), then apply the audit-length caps to the redacted text.
        redacted_command = redact_secrets(command)
        cmd_truncated = False
        if decision == "deny":
            if len(redacted_command) > _MAX_DENIED_COMMAND_LOG_CHARS:
                logged_command = redacted_command[:_MAX_DENIED_COMMAND_LOG_CHARS]
                cmd_truncated = True
            else:
                logged_command = redacted_command
        else:
            logged_command = redacted_command[:500]

        payload: dict[str, Any] = {
            "event": "shell_guard",
            "conversation_id": conversation_id,
            "correlation_id": correlation_id,
            "command": logged_command,
            "decision": decision,
            "reason": reason,
            "hook_duration_ms": hook_ms,
        }
        if decision == "deny":
            payload["permission_denied"] = True
        if cmd_truncated:
            payload["command_truncated"] = True
        log_event(payload)

        # The decision goes to Cursor FIRST. Telemetry is emitted afterwards,
        # isolated in its own try/except, so an emit failure can never reach
        # the outer fallback and downgrade a computed deny/ask to allow.
        write_stdout(cursor_response)

        try:
            send_event(
                "tool.executed",
                {
                    "session_id": conversation_id,
                    "correlation_id": correlation_id,
                    "tool_name": "shell",
                    "decision": decision,
                    "command_preview": sanitize_preview(command),
                    "agent_source": "cursor",
                },
            )
        except Exception:
            pass
    except Exception:
        write_stdout({"permission": "allow"})


if __name__ == "__main__":
    main()

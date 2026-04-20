"""beforeShellExecution hook — two-tier shell command guard.

Ported to .cursor/hooks/scripts/ to use the shared lib layer.
This hook CAN control execution. Return deny to block, allow to proceed.

Correlation threading
  Reads ``latest_correlation_id`` from ``~/.omnicursor/sessions/current.json``
  (written by Event 1 on every beforeSubmitPrompt call) so shell guard events
  in events.jsonl link back to the prompt that triggered them.

Typed event schema
  Every call logs: event, conversation_id, correlation_id, command (≤500 chars),
  decision, reason, hook_duration_ms.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from _common import log_event, read_session_context, read_stdin, write_stdout


# ---------------------------------------------------------------------------
# Patterns — compiled at module load
# ---------------------------------------------------------------------------

# HARD_BLOCK patterns hand-picked for OmniCursor; inspired by omniclaude bash_guard.py
# but not a direct import — 9 patterns covering rm-rf, mkfs, dd, fork-bomb, --no-verify, etc.
# Future sync job should reconcile any drift against the omniclaude source.
HARD_BLOCK: List[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+/\s*$",
        r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+~/?\s*$",
        r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+/\*",
        r"\bmkfs\b",
        r"\bdd\s+if=.*\s+of=/dev/",
        r":\(\)\s*\{\s*:\|:&\s*\}\s*;:",
        r"--no-verify",
        r">\s*/dev/sda",
        r"base64\s+--decode\s*\|.*\bsh\b",
    ]
]

# SOFT_WARN patterns hand-picked for OmniCursor — 11 patterns covering force-push,
# hard-reset, DROP TABLE, kill -9, chmod 777, sudo rm, eval, and curl/wget pipe-to-shell.
# Not present in omniclaude bash_guard.py (which only hard-blocks); advisory tier is OmniCursor-native.
SOFT_WARN: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(p, re.IGNORECASE), reason)
    for p, reason in [
        (r"git\s+push\s+--force", "Force push can destroy remote history"),
        (r"git\s+push\s+-f\b", "Force push can destroy remote history"),
        (r"git\s+reset\s+--hard", "Hard reset discards uncommitted changes"),
        (r"\bDROP\s+(TABLE|DATABASE)\b", "Destructive SQL operation"),
        (r"\bTRUNCATE\b", "Destructive SQL operation"),
        (r"curl\s+.*\|\s*(ba)?sh", "Piping remote script to shell is dangerous"),
        (r"wget\s+.*\|\s*(ba)?sh", "Piping remote script to shell is dangerous"),
        (r"\bkill\s+-9\b", "SIGKILL does not allow graceful shutdown"),
        (r"\bchmod\s+777\b", "World-writable permissions are a security risk"),
        (r"\bsudo\s+rm\b", "Elevated removal is risky"),
        (r"\beval\b", "eval executes arbitrary strings as code"),
    ]
]


# ---------------------------------------------------------------------------
# Guard logic
# ---------------------------------------------------------------------------


def guard_command(command: str) -> Dict[str, Any]:
    """Return Cursor hook response JSON for *command*."""
    if not command:
        return {"permission": "allow"}

    # Tier 1 — HARD_BLOCK
    for pattern in HARD_BLOCK:
        if pattern.search(command):
            return {
                "permission": "deny",
                "userMessage": f"Blocked: command matches a destructive pattern ({pattern.pattern})",
            }

    # Tier 2 — SOFT_WARN
    for pattern, reason in SOFT_WARN:
        if pattern.search(command):
            return {
                "permission": "allow",
                "agentMessage": f"Warning: {reason}. Proceeding.",
            }

    # Default — allow
    return {"permission": "allow"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _start = time.monotonic()
    try:
        data = read_stdin()
        command = data.get("command", "")
        conversation_id = data.get("conversation_id", "")

        # Read correlation_id written by Event 1 for this prompt.
        session = read_session_context()
        correlation_id: str = session.get("latest_correlation_id", "")

        response = guard_command(command)

        if response.get("permission") == "deny":
            decision = "deny"
            reason = response.get("userMessage", "")
        elif "agentMessage" in response:
            decision = "warn"
            reason = response.get("agentMessage", "")
        else:
            decision = "allow"
            reason = ""

        hook_ms = int((time.monotonic() - _start) * 1000)

        log_event({
            "event": "shell_guard",
            "conversation_id": conversation_id,
            "correlation_id": correlation_id,
            "command": command[:500],
            "decision": decision,
            "reason": reason,
            "hook_duration_ms": hook_ms,
        })

        write_stdout(response)
    except Exception:
        write_stdout({"permission": "allow"})


if __name__ == "__main__":
    main()

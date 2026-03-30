"""beforeShellExecution hook — two-tier shell command guard.

This hook CAN control execution. Return deny to block, allow to proceed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import log_event, read_stdin, write_stdout


# ---------------------------------------------------------------------------
# Patterns — compiled at module load
# ---------------------------------------------------------------------------

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
    ]
]

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
    try:
        data = read_stdin()
        command = data.get("command", "")
        conversation_id = data.get("conversation_id", "")

        response = guard_command(command)

        # Determine decision label for logging
        if response.get("permission") == "deny":
            decision = "deny"
            reason = response.get("userMessage", "")
        elif "agentMessage" in response:
            decision = "warn"
            reason = response.get("agentMessage", "")
        else:
            decision = "allow"
            reason = ""

        log_event(
            {
                "event": "shell_guard",
                "command": command[:500],
                "decision": decision,
                "reason": reason,
                "conversation_id": conversation_id,
            }
        )

        write_stdout(response)
    except Exception:
        write_stdout({"permission": "allow"})


if __name__ == "__main__":
    main()

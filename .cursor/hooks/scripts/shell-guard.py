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

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from _common import (
    SESSIONS_DIR,
    log_event,
    read_session_context,
    read_session_json,
    read_stdin,
    write_stdout,
)

_HOOKS_DIR: Path = Path(__file__).resolve().parent.parent
_DOD_CONFIG_PATH: Path = _HOOKS_DIR / "config" / "dod_enforcement.json"


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
# DoD + dispatch claim (Phase 1 migration)
# ---------------------------------------------------------------------------


def _load_dod_config() -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "dod_enabled": False,
        "dod_linear_transition_regex": "",
        "dispatch_enabled": False,
        "dispatch_claim_regexes": [],
    }
    try:
        raw = json.loads(_DOD_CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            merged = {**defaults, **raw}
            if not isinstance(merged.get("dispatch_claim_regexes"), list):
                merged["dispatch_claim_regexes"] = []
            return merged
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return defaults


def _dispatch_claim_path(conversation_id: str, sessions_root: Path) -> Path:
    return sessions_root / conversation_id / "dispatch_claim"


def guard_command(
    command: str,
    *,
    conversation_id: str = "",
    sessions_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return Cursor hook response JSON for *command*."""
    if not command:
        return {"permission": "allow"}

    sessions_base = sessions_root if sessions_root is not None else None
    cfg = _load_dod_config()

    # Tier 1 — HARD_BLOCK
    for pattern in HARD_BLOCK:
        if pattern.search(command):
            return {
                "permission": "deny",
                "userMessage": f"Blocked: command matches a destructive pattern ({pattern.pattern})",
            }

    # Tier 1b — Definition-of-Done (Linear transition requires CI signal in session)
    if (
        conversation_id
        and cfg.get("dod_enabled")
        and os.environ.get("OMNICURSOR_DOD_BYPASS", "") != "1"
    ):
        dod_rx = str(cfg.get("dod_linear_transition_regex") or "")
        try:
            dod_match = bool(dod_rx and re.search(dod_rx, command))
        except re.error:
            dod_match = False
        if dod_match:
            state = read_session_json(conversation_id, sessions_root=sessions_base)
            if not state.get("ci_passing"):
                return {
                    "permission": "deny",
                    "userMessage": (
                        "Blocked (DoD): Linear done/completed transitions require "
                        "`ci_passing: true` in ~/.omnicursor/sessions/<conversation_id>.json "
                        "(set after CI green) or set OMNICURSOR_DOD_BYPASS=1 for local dev."
                    ),
                }

    # Tier 1c — Dispatch claim file for configured medium-risk commands
    if (
        conversation_id
        and cfg.get("dispatch_enabled")
        and os.environ.get("OMNICURSOR_DISPATCH_BYPASS", "") != "1"
    ):
        patterns = cfg.get("dispatch_claim_regexes") or []
        for pat in patterns:
            if not pat or not isinstance(pat, str):
                continue
            try:
                if re.search(pat, command):
                    root = sessions_base if sessions_base is not None else SESSIONS_DIR
                    claim = _dispatch_claim_path(conversation_id, root)
                    if not claim.exists():
                        return {
                            "permission": "deny",
                            "userMessage": (
                                "Blocked (dispatch claim): touch "
                                f"{claim} after registering intent, or set "
                                "OMNICURSOR_DISPATCH_BYPASS=1."
                            ),
                        }
            except re.error:
                continue

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

        response = guard_command(command, conversation_id=conversation_id)

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

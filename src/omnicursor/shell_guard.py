# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Shell-guard business logic shared by node_cursor_shell_guard_effect.

Extracted from .cursor/hooks/scripts/shell-guard.py. The hook script retains
its own copy for stdlib-only execution; this module is the importable version
for node handlers and tests.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# HARD_BLOCK patterns — 9 patterns covering rm-rf, mkfs, dd, fork-bomb, --no-verify.
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

# SOFT_WARN patterns — 11 advisory-tier patterns (OmniCursor-native).
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
        (r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+\S+", "Recursive force removal — verify the target path"),
    ]
]


def _load_dod_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "dod_enabled": False,
        "dod_linear_transition_regex": "",
        "dispatch_enabled": False,
        "dispatch_claim_regexes": [],
    }
    if config_path is None:
        return defaults
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            merged = {**defaults, **raw}
            if not isinstance(merged.get("dispatch_claim_regexes"), list):
                merged["dispatch_claim_regexes"] = []
            return merged
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return defaults


def guard_command(
    command: str,
    *,
    conversation_id: str = "",
    sessions_root: Optional[Path] = None,
    dod_config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return Cursor hook response dict for *command*."""
    if not command:
        return {"permission": "allow"}

    cfg = _load_dod_config(dod_config_path)

    # Tier 1 — HARD_BLOCK
    for pattern in HARD_BLOCK:
        if pattern.search(command):
            return {
                "permission": "deny",
                "userMessage": f"Blocked: command matches a destructive pattern ({pattern.pattern})",
            }

    # Tier 1b — DoD (disabled by default; enabled via dod_config_path)
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
            root = sessions_root or (Path.home() / ".omnicursor" / "sessions")
            state_path = root / f"{conversation_id}.json"
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                state = {}
            if not state.get("ci_passing"):
                return {
                    "permission": "deny",
                    "userMessage": (
                        "Blocked (DoD): Linear done/completed transitions require "
                        "`ci_passing: true` in ~/.omnicursor/sessions/<conversation_id>.json "
                        "or set OMNICURSOR_DOD_BYPASS=1 for local dev."
                    ),
                }

    # Tier 1c — Dispatch claim (disabled by default)
    if (
        conversation_id
        and cfg.get("dispatch_enabled")
        and os.environ.get("OMNICURSOR_DISPATCH_BYPASS", "") != "1"
    ):
        root = sessions_root or (Path.home() / ".omnicursor" / "sessions")
        patterns = cfg.get("dispatch_claim_regexes") or []
        for pat in patterns:
            if not pat or not isinstance(pat, str):
                continue
            try:
                if re.search(pat, command):
                    claim = root / conversation_id / "dispatch_claim"
                    if not claim.exists():
                        return {
                            "permission": "deny",
                            "userMessage": (
                                f"Blocked (dispatch claim): touch {claim} after "
                                "registering intent, or set OMNICURSOR_DISPATCH_BYPASS=1."
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

    return {"permission": "allow"}

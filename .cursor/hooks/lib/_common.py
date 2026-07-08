"""Shared utilities for OmniCursor Cursor hooks (shared lib).

Only Python stdlib — no third-party imports.

Adapted from .cursor/hooks/_common.py.
Key differences from the top-level _common.py:
  - Path resolution: lib/ is at .cursor/hooks/lib/, so REPO_ROOT goes up 3
    levels (.cursor/hooks/lib → .cursor/hooks → .cursor → project root).
  - AGENTS_DIR still points to .cursor/agents/ — agent JSON configs are shared.
  - write_context() outputs Cursor's {"systemMessage": ...} envelope.
    Use write_stdout() for raw decision responses (PreToolUse blocks, etc.).
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# .cursor/hooks/lib/_common.py  →  parent chain:
#   lib/       (.parent)
#   hooks/     (.parent)
#   .cursor/   (.parent)
#   REPO_ROOT  (.parent)
LIB_DIR: Path = Path(__file__).resolve().parent
HOOKS_DIR: Path = LIB_DIR.parent           # .cursor/hooks/
CURSOR_DIR: Path = HOOKS_DIR.parent        # .cursor/
REPO_ROOT: Path = CURSOR_DIR.parent        # project root

AGENTS_DIR: Path = CURSOR_DIR / "agents"

OMNICURSOR_DIR: Path = Path.home() / ".omnicursor"
EVENTS_LOG: Path = OMNICURSOR_DIR / "events.jsonl"
SESSIONS_DIR: Path = OMNICURSOR_DIR / "sessions"
LEARNED_PATTERNS_FILE: Path = OMNICURSOR_DIR / "learned_patterns.json"
SEED_PATTERNS_FILE: Path = HOOKS_DIR / "data" / "seed_patterns.json"


# ---------------------------------------------------------------------------
# Kill-switch + per-hook mask (A6)
# ---------------------------------------------------------------------------

# Canonical short names for the 7 hook scripts, as accepted by
# OMNICURSOR_HOOKS_MASK. Aliases cover the script filename and Cursor's native
# event name so operators don't have to remember which spelling wins.
# (Vocabulary shipped as a default — ratify in PR review.)
_HOOK_ALIASES: Dict[str, str] = {
    # session-start.py (sessionStart)
    "session-start": "session-start",
    "sessionstart": "session-start",
    "start": "session-start",
    # user-prompt-submit.py (beforeSubmitPrompt)
    "prompt": "prompt",
    "user-prompt-submit": "prompt",
    "beforesubmitprompt": "prompt",
    # shell-guard.py (beforeShellExecution)
    "shell": "shell",
    "shell-guard": "shell",
    "beforeshellexecution": "shell",
    # post-edit.py (afterFileEdit)
    "edit": "edit",
    "post-edit": "edit",
    "afterfileedit": "edit",
    # post-tool-use.py (postToolUse)
    "tool": "tool",
    "post-tool-use": "tool",
    "posttooluse": "tool",
    # stop.py (stop)
    "stop": "stop",
    # session-end.py (sessionEnd)
    "session-end": "session-end",
    "sessionend": "session-end",
    "end": "session-end",
}


def _normalize_hook_name(name: str) -> str:
    token = name.strip().lower().replace("_", "-")
    return _HOOK_ALIASES.get(token, token)


def hooks_disabled() -> bool:
    """Global kill-switch for every hook side effect (A6).

    Returns True if either:
    - env var OMNICURSOR_HOOKS_DISABLE=1, or
    - file ~/.omnicursor/hooks-disabled exists.

    Mirrors omniclaude's ``_hooks_disabled()`` (``hook_runtime/server.py``).
    Kept a plain module function so all 7 hook scripts apply identical
    semantics and the check stays cheap. ``Path.home()`` is resolved at call
    time (not import time) so a sandboxed ``HOME`` (tests, smoke runs) is
    honored.
    """
    if os.environ.get("OMNICURSOR_HOOKS_DISABLE") == "1":
        return True
    if (Path.home() / ".omnicursor" / "hooks-disabled").exists():
        return True
    return False


def hook_enabled(hook_name: str) -> bool:
    """Combined per-hook gate: global kill-switch + OMNICURSOR_HOOKS_MASK.

    ``OMNICURSOR_HOOKS_MASK`` is a comma-separated allowlist of hook short
    names (e.g. ``"prompt,shell"`` — see ``_HOOK_ALIASES`` for the accepted
    spellings). Unset or blank means every hook is enabled; when set, only the
    named hooks run and every other hook short-circuits to its benign output.
    A deliberately simple env toggle — NOT coupled to ``EnumHookBit`` ordinals.

    Each script calls this first thing in ``main()``, before reading stdin or
    performing any side effect (daemon-ensure, pattern fetch, emit, injection
    write, local log).
    """
    if hooks_disabled():
        return False
    mask = os.environ.get("OMNICURSOR_HOOKS_MASK")
    if mask is None or not mask.strip():
        return True
    enabled = {_normalize_hook_name(t) for t in mask.split(",") if t.strip()}
    return _normalize_hook_name(hook_name) in enabled


# ---------------------------------------------------------------------------
# Per-conversation session JSON (~/.omnicursor/sessions/<id>.json)
# ---------------------------------------------------------------------------


def session_json_path(
    conversation_id: str,
    *,
    sessions_root: Optional[Path] = None,
) -> Path:
    root = sessions_root if sessions_root is not None else SESSIONS_DIR
    return root / f"{conversation_id}.json"


def read_session_json(
    conversation_id: str,
    *,
    sessions_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Read merged session state; returns {} if missing or invalid."""
    if not conversation_id:
        return {}
    root = sessions_root if sessions_root is not None else SESSIONS_DIR
    path = root / f"{conversation_id}.json"
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def merge_session_json(
    conversation_id: str,
    updates: Dict[str, Any],
    *,
    sessions_root: Optional[Path] = None,
) -> None:
    """Merge *updates* into sessions/<id>.json (create if absent). Never raises."""
    if not conversation_id:
        return
    try:
        ensure_dirs()
        path = session_json_path(conversation_id, sessions_root=sessions_root)
        data = read_session_json(conversation_id, sessions_root=sessions_root)
        data.update(updates)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------


def ensure_dirs() -> None:
    """Create ~/.omnicursor/ and sessions/ if they don't exist."""
    try:
        OMNICURSOR_DIR.mkdir(parents=True, exist_ok=True)
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Stdin / stdout helpers
# ---------------------------------------------------------------------------


def read_stdin() -> Dict[str, Any]:
    """Read JSON from stdin. Returns {} on any failure."""
    try:
        raw = sys.stdin.read()
        if not raw or not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def write_stdout(data: Dict[str, Any]) -> None:
    """Write a plain JSON dict to stdout.

    Use for hook responses that have their own top-level shape, e.g.
    ``{"permission": "deny", "userMessage": "..."}`` for beforeShellExecution.
    """
    print(json.dumps(data))


def write_context(content: str) -> None:
    """DEPRECATED — Cursor's ``beforeSubmitPrompt`` does NOT consume ``systemMessage``.

    Cursor's real ``beforeSubmitPrompt`` output schema is ``{continue, user_message}``
    only; a ``{"systemMessage": ...}`` envelope is silently ignored, so this was a
    structural no-op. Live context injection flows through
    ``sessionStart.additional_context`` (initial system context) and
    ``postToolUse.additional_context`` (mid-session refresh) — use
    :func:`write_additional_context` from those hooks instead. Retained only so any
    stale caller keeps exiting cleanly.
    """
    print(json.dumps({"systemMessage": content}))


def write_additional_context(
    content: str,
    *,
    env: Optional[Dict[str, str]] = None,
) -> None:
    """Write an ``additional_context`` injection response to stdout.

    This is Cursor's real context-injection envelope, consumed by the
    ``sessionStart`` and ``postToolUse`` hooks:

        {"additional_context": "<markdown>", "env": {"KEY": "VALUE"}}

    *content* is injected into the conversation's system context. *env*, when
    provided (sessionStart only), is exported to all subsequent hook executions
    within the session. Empty *content* with no *env* emits ``{}`` (a valid no-op
    response) so the hook never blocks.
    """
    response: Dict[str, Any] = {}
    if content:
        response["additional_context"] = content
    if env:
        response["env"] = env
    print(json.dumps(response))


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------


def log_event(event: Dict[str, Any]) -> None:
    """Append a timestamped JSON line to events.jsonl. Never raises."""
    try:
        ensure_dirs()
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            **event,
        }
        with EVENTS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Agent config loading
# ---------------------------------------------------------------------------


def read_session_context() -> Dict[str, Any]:
    """Read the active session from ~/.omnicursor/sessions/current.json.

    Returns the dict written by Event 1's _init_session / _update_session_correlation,
    which includes ``conversation_id``, ``started_at``, and ``latest_correlation_id``.
    Returns {} if the file is absent or unreadable — callers must handle the empty case.
    """
    try:
        current = SESSIONS_DIR / "current.json"
        if not current.exists():
            return {}
        return json.loads(current.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------


def load_agent_configs() -> List[Dict[str, Any]]:
    """Load all .json files from .cursor/agents/. Returns [] on failure."""
    configs: List[Dict[str, Any]] = []
    try:
        if not AGENTS_DIR.is_dir():
            return configs
        for path in sorted(AGENTS_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    configs.append(data)
            except (json.JSONDecodeError, OSError):
                continue
    except OSError:
        pass
    return configs

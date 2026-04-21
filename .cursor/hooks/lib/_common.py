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
    """Write a prompt enrichment response to stdout.

    Wraps *content* in Cursor's ``{"systemMessage": ...}`` envelope.
    The string should be plain Markdown — Cursor injects it as a system
    message before the model responds.
    """
    print(json.dumps({"systemMessage": content}))


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

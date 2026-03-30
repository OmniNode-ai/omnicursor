"""Shared utilities for OmniCursor Cursor hooks.

Only Python stdlib — no third-party imports.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HOOKS_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = HOOKS_DIR.parent.parent
AGENTS_DIR: Path = HOOKS_DIR.parent / "agents"

OMNICURSOR_DIR: Path = Path.home() / ".omnicursor"
EVENTS_LOG: Path = OMNICURSOR_DIR / "events.jsonl"
SESSIONS_DIR: Path = OMNICURSOR_DIR / "sessions"


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
    """Write JSON to stdout."""
    print(json.dumps(data))


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

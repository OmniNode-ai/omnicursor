"""Durable local outbox for OmniCursor session outcomes.

Appends one JSON line per session to ~/.omnicursor/outbox.jsonl.
The outbox is the contract-frozen payload that Option C will drain to
Kafka / OmniIntelligence when ready.

Stdlib only. Never raises — failures are silently swallowed so the stop
hook is never blocked by outbox I/O errors.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _outbox_path(override: Optional[Path] = None) -> Path:
    if override is not None:
        return override
    env = os.environ.get("OMNICURSOR_OUTBOX_FILE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".omnicursor" / "outbox.jsonl"


def write_session_outcome(
    payload: Dict[str, Any],
    *,
    outbox_path: Optional[Path] = None,
) -> bool:
    """Append *payload* as a single JSON line to the outbox file.

    Returns True on success, False on any I/O error.  Never raises.

    POSIX append is atomic for writes up to PIPE_BUF (~4 KB on macOS/Linux).
    Session payloads are well under that limit, so no file-level locking is
    needed in Option B mínima.  If concurrent-write safety becomes a concern
    in Option C, add fcntl.flock here.
    """
    path = _outbox_path(outbox_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        return True
    except Exception:
        return False

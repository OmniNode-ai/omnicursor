"""Shim — delegates to the canonical implementation in src/omnicursor/sync/pattern_sync.py.

stop.py injects <repo>/src into sys.path (lines 18-19) before importing this module,
so the import below always resolves correctly at runtime.

Pull learned patterns from omniintelligence into ~/.omnicursor/learned_patterns.json.
Stdlib only. Safe no-op when the service is down or in stub mode.

**Capstone:** stop.py calls this only when ``OMNICURSOR_PATTERN_SYNC_HTTP`` is truthy
(``1`` / ``true`` / ``yes``). Default is off.
"""

from __future__ import annotations

from pathlib import Path

from omnicursor.sync.pattern_sync import run as _run


def sync_learned_patterns(target_file: Path, *, timeout_s: float = 3.0) -> bool:
    """GET /api/v1/patterns and write {\"patterns\": [...]} for pattern_loader.

    Returns True if the file was written from a successful HTTP response.
    """
    return _run(target_file, timeout_s=timeout_s)

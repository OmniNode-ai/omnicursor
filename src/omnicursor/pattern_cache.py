# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Thread-safe in-memory pattern cache — canonical source of truth.

Shared by:
  - .cursor/hooks/pattern_loader.py  (shim re-exports from here)
  - .cursor/hooks/lib/pattern_loader.py  (shim re-exports from here)

Stdlib-only (json, threading, time, pathlib).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_STALE_SECONDS: int = 600


class PatternCache:
    """Thread-safe in-memory cache of learned patterns keyed by domain.

    Designed for the beforeSubmitPrompt hook hot path.
    Warm from a JSON file on first use, then read from memory.
    """

    def __init__(self, stale_seconds: int = _DEFAULT_STALE_SECONDS) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._last_updated_at: Optional[float] = None
        self._stale_seconds = stale_seconds

    def get(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return cached patterns for domain. Returns [] if missing."""
        key = domain or "general"
        with self._lock:
            return list(self._data.get(key, []))

    def update(self, domain: str, patterns: List[Dict[str, Any]]) -> None:
        """Replace cached patterns for domain and reset staleness clock."""
        with self._lock:
            self._data[domain] = list(patterns)
            self._last_updated_at = time.monotonic()

    def is_warm(self) -> bool:
        """Return True if the cache has been populated at least once."""
        with self._lock:
            return self._last_updated_at is not None

    def is_stale(self) -> bool:
        """Return True if the cache has not been updated within the threshold."""
        with self._lock:
            if self._last_updated_at is None:
                return True
            return (time.monotonic() - self._last_updated_at) > self._stale_seconds

    def warm_from_json(self, path: Path) -> int:
        """Load patterns from a JSON file and populate the cache.

        Returns the number of patterns loaded. Does not raise on errors.
        """
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            patterns = data.get("patterns", [])
            if not isinstance(patterns, list):
                return 0

            by_domain: Dict[str, List[Dict[str, Any]]] = {}
            for p in patterns:
                if not isinstance(p, dict):
                    continue
                domain = p.get("domain", "general")
                by_domain.setdefault(domain, []).append(p)

            with self._lock:
                self._data = by_domain
                self._last_updated_at = time.monotonic()

            return len(patterns)
        except (json.JSONDecodeError, OSError, KeyError):
            return 0

    def clear(self) -> None:
        """Reset the cache to empty (cold) state."""
        with self._lock:
            self._data.clear()
            self._last_updated_at = None


_CACHE = PatternCache()


def get_pattern_cache() -> PatternCache:
    """Return the module-level singleton cache."""
    return _CACHE

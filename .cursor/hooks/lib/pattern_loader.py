"""Thread-safe in-memory pattern cache for the user-prompt-submit.py hot path.

Copied from .cursor/hooks/pattern_loader.py — no changes required.
The cache is keyed by domain (e.g. "hooks", "git", "testing").  On first use
it warms from ``~/.omnicursor/learned_patterns.json``.  Subsequent reads are
pure dict lookups behind an RLock.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


_DEFAULT_STALE_SECONDS: int = 600


class PatternCache:
    """Thread-safe in-memory cache of learned patterns keyed by domain."""

    def __init__(self, stale_seconds: int = _DEFAULT_STALE_SECONDS) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._last_updated_at: Optional[float] = None
        self._stale_seconds = stale_seconds

    def get(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        key = domain or "general"
        with self._lock:
            return list(self._data.get(key, []))

    def update(self, domain: str, patterns: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._data[domain] = list(patterns)
            self._last_updated_at = time.monotonic()

    def is_warm(self) -> bool:
        with self._lock:
            return self._last_updated_at is not None

    def is_stale(self) -> bool:
        with self._lock:
            if self._last_updated_at is None:
                return True
            return (time.monotonic() - self._last_updated_at) > self._stale_seconds

    def warm_from_json(self, path: Path) -> int:
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
        with self._lock:
            self._data.clear()
            self._last_updated_at = None


_CACHE = PatternCache()


def get_pattern_cache() -> PatternCache:
    return _CACHE

"""Fetch learned patterns from omniintelligence into learned_patterns.json.

Used by tests and optional tooling. Hooks invoke the stdlib copy in
``.cursor/hooks/lib/pattern_sync.py`` only when ``OMNICURSOR_PATTERN_SYNC_HTTP`` is set
(dev / experimentation — not the default capstone path).
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


def _base_url(override: Optional[str]) -> str:
    return (
        override
        or os.environ.get("OMNIINTELLIGENCE_URL")
        or "http://127.0.0.1:18091"
    ).rstrip("/")


def _probe_health(base: str, *, timeout_s: float) -> bool:
    """GET /health. Return True only on a clean 200 response."""
    url = f"{base}/health"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s):
            return True
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False


def run(
    target_file: Optional[Path] = None,
    *,
    base_url: Optional[str] = None,
    timeout_s: float = 3.0,
) -> bool:
    """GET /api/v1/patterns and write ``{"patterns": [...]}``.

    Probes /health first; returns False without touching the target file if the
    service is offline, returning stub responses, or sending an unexpected body.

    Returns True if a response was written successfully.
    """
    path = target_file or (Path.home() / ".omnicursor" / "learned_patterns.json")
    base = _base_url(base_url)

    if not _probe_health(base, timeout_s=min(1.0, timeout_s)):
        return False

    url = f"{base}/api/v1/patterns"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
        body: Any = json.loads(raw)
        if isinstance(body, list):
            normalized: dict[str, Any] = {"patterns": body}
        elif isinstance(body, dict) and isinstance(body.get("patterns"), list):
            normalized = {"patterns": body["patterns"]}
        else:
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(normalized, indent=2, ensure_ascii=False) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=str(path.parent),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_path, path)
        except Exception:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise
        return True
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TypeError):
        return False

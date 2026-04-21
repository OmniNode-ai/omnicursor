"""Pull learned patterns from omniintelligence into ~/.omnicursor/learned_patterns.json.

Stdlib only (urllib). Safe no-op when the service is down.

**Capstone:** `stop.py` calls this only when ``OMNICURSOR_PATTERN_SYNC_HTTP`` is truthy
(``1`` / ``true`` / ``yes``). Default is off — authoritative pattern persistence is
local / PostgreSQL per sponsor alignment (see ``docs/dev/SPONSOR_ALIGNMENT_2026-04-16.md``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict


def _default_base_url() -> str:
    return os.environ.get("OMNIINTELLIGENCE_URL", "http://127.0.0.1:8053").rstrip("/")


def sync_learned_patterns(target_file: Path, *, timeout_s: float = 3.0) -> bool:
    """GET /api/v1/patterns and write {\"patterns\": [...]} for pattern_loader.

    Returns True if the file was written from a successful HTTP response.
    """
    url = f"{_default_base_url()}/api/v1/patterns"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
        body: Any = json.loads(raw)
        if isinstance(body, list):
            normalized: Dict[str, Any] = {"patterns": body}
        elif isinstance(body, dict) and "patterns" in body:
            normalized = {"patterns": body.get("patterns", [])}
        else:
            normalized = {"patterns": []}
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TypeError):
        return False

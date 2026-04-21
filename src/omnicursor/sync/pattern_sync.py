"""Fetch learned patterns from omniintelligence into learned_patterns.json.

Used by tests and optional tooling. Hooks invoke the stdlib copy in
``.cursor/hooks/lib/pattern_sync.py`` only when ``OMNICURSOR_PATTERN_SYNC_HTTP`` is set
(dev / experimentation — not the default capstone path).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


def run(
    target_file: Optional[Path] = None,
    *,
    base_url: Optional[str] = None,
    timeout_s: float = 3.0,
) -> bool:
    """GET /api/v1/patterns and write ``{\"patterns\": [...]}``.

    Returns True if a response was written successfully.
    """
    path = target_file or (Path.home() / ".omnicursor" / "learned_patterns.json")
    base = (base_url or os.environ.get("OMNIINTELLIGENCE_URL") or "http://127.0.0.1:8053").rstrip(
        "/"
    )
    url = f"{base}/api/v1/patterns"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
        body: Any = json.loads(raw)
        if isinstance(body, list):
            normalized: dict[str, Any] = {"patterns": body}
        elif isinstance(body, dict) and "patterns" in body:
            normalized = {"patterns": body.get("patterns", [])}
        else:
            normalized = {"patterns": []}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TypeError):
        return False

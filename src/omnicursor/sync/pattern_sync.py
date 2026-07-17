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


_DEFAULT_BASE_URL = "http://localhost:18091"


class PatternSyncConfigError(ValueError):
    """A configured service URL is invalid (non-http(s) scheme).

    Raised instead of silently substituting the default URL: a typo'd
    INTELLIGENCE_SERVICE_URL must not redirect pattern traffic to localhost
    behind the operator's back. Hook callers wrap sync in a blanket
    ``except Exception`` (session-start.py), so for them this fails closed
    as a no-op sync.
    """


def _base_url(override: Optional[str]) -> str:
    # Single-sourced on INTELLIGENCE_SERVICE_URL — the same env var the hooks
    # read (lib/context_injection.py). OMNIINTELLIGENCE_URL is a deprecated
    # fallback kept for one release.
    base = (
        override
        or os.environ.get("INTELLIGENCE_SERVICE_URL")
        or os.environ.get("OMNIINTELLIGENCE_URL")
        or _DEFAULT_BASE_URL
    ).rstrip("/")
    # urlopen accepts file:// and custom schemes; constrain env/override input
    # to http(s) so a misconfigured URL can't read local files (bandit B310).
    if not base.startswith(("http://", "https://")):
        raise PatternSyncConfigError(
            f"pattern-sync service URL must be http(s), got: {base!r}"
        )
    return base


def _probe_health(base: str, *, timeout_s: float) -> bool:
    """GET /health. Return True only on a clean 200 response."""
    url = f"{base}/health"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        # Scheme constrained to http(s) by _base_url.
        with urllib.request.urlopen(req, timeout=timeout_s):  # nosec B310
            return True
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False


def _read_local_patterns(path: Path) -> list[Any]:
    """Read local patterns file and return a normalized list."""
    try:
        if not path.exists():
            return []
        body: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []

    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        patterns = body.get("patterns")
        if isinstance(patterns, list):
            return patterns
    return []


def _pattern_identity(pattern: Any) -> str:
    """Best-effort stable identity for de-duplication."""
    if isinstance(pattern, dict):
        pattern_id = pattern.get("pattern_id")
        if isinstance(pattern_id, str) and pattern_id:
            return f"pattern_id:{pattern_id}"
    try:
        return f"json:{json.dumps(pattern, sort_keys=True, ensure_ascii=False)}"
    except (TypeError, ValueError):
        return f"repr:{repr(pattern)}"


def _merge_patterns(local_patterns: list[Any], remote_patterns: list[Any]) -> list[Any]:
    """Keep local patterns and append only new remote patterns."""
    merged = list(local_patterns)
    seen = {_pattern_identity(item) for item in local_patterns}
    for pattern in remote_patterns:
        identity = _pattern_identity(pattern)
        if identity in seen:
            continue
        merged.append(pattern)
        seen.add(identity)
    return merged


def run(
    target_file: Optional[Path] = None,
    *,
    base_url: Optional[str] = None,
    timeout_s: float = 3.0,
) -> bool:
    """Merge local patterns with GET /api/v1/patterns and write output.

    Probes /health first; returns False without touching the target file if the
    service is offline. Local patterns are preserved — remote patterns are
    appended only if not already present (local takes priority).

    Returns True if remote patterns were fetched and merged. Raises
    PatternSyncConfigError if the configured URL has a non-http(s) scheme.
    """
    path = target_file or (Path.home() / ".omnicursor" / "learned_patterns.json")
    base = _base_url(base_url)

    if not _probe_health(base, timeout_s=min(1.0, timeout_s)):
        return False

    local_patterns = _read_local_patterns(path)
    url = f"{base}/api/v1/patterns"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        # Scheme constrained to http(s) by _base_url.
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # nosec B310
            raw = resp.read().decode("utf-8")
        body: Any = json.loads(raw)
        if isinstance(body, list):
            remote_patterns: list[Any] = body
        elif isinstance(body, dict) and isinstance(body.get("patterns"), list):
            remote_patterns = body["patterns"]
        else:
            return False
        normalized: dict[str, Any] = {
            "patterns": _merge_patterns(local_patterns, remote_patterns)
        }
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
    except (
        OSError,
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        TypeError,
    ):
        return False

"""Shared context-injection logic for the sessionStart / postToolUse hooks.

Cursor exposes exactly two live context-injection channels:

  - ``sessionStart.additional_context`` — the conversation's initial system
    context (injected once, when a composer conversation is created).
  - ``postToolUse.additional_context`` — a mid-session refresh applied after a
    tool executes.

``beforeSubmitPrompt`` is block-only (``{continue, user_message}``) and CANNOT
inject, so per-prompt routing is emitted for backend learning but not injected;
the injected context is session-level (sessionStart) and tool-activity-refreshed
(postToolUse). This module builds the markdown blocks and owns the single source
of truth for the intelligence service URL (drift-consolidated from the old
hardcoded ``:18091`` sites).

Stdlib only. Every function degrades gracefully — network/file failures fall back
to a local cache or an empty result so a hook is never blocked.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from _common import (
    LEARNED_PATTERNS_FILE,
    SEED_PATTERNS_FILE,
    SESSIONS_DIR,
)
from pattern_loader import get_pattern_cache
from prompt_pattern_selection import (
    MAX_PATTERNS,
    filter_patterns_by_relevance,
)
from redaction import sanitize_pattern_text

# --- Single source of truth for the intelligence service URL (drift cleanup) ---
INTELLIGENCE_SERVICE_URL: str = os.environ.get(
    "INTELLIGENCE_SERVICE_URL",
    "http://localhost:18091",
).rstrip("/")

_API_TIMEOUT_S: float = (
    float(os.environ.get("OMNICURSOR_CONTEXT_API_TIMEOUT_MS", "900")) / 1000.0
)
_API_FETCH_LIMIT: int = 50

DELEGATION_THRESHOLD: int = 2


# ---------------------------------------------------------------------------
# Domain inference
# ---------------------------------------------------------------------------


def agent_domain(agent_name: str) -> str:
    """Normalize an agent name to a pattern domain (e.g. ``agent-debug`` -> ``debug``)."""
    domain = (agent_name or "").lower()
    for prefix in ("agent-", "omnicursor-"):
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]
            break
    return domain.replace("-", "_") or "general"


_EXT_DOMAIN = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".md": "docs",
    ".yaml": "config",
    ".yml": "config",
    ".json": "config",
    ".sql": "database",
}


def infer_domain_from_path(file_path: str) -> str:
    """Best-effort domain from a file path's extension; ``general`` when unknown."""
    if not file_path:
        return "general"
    return _EXT_DOMAIN.get(Path(file_path).suffix.lower(), "general")


# ---------------------------------------------------------------------------
# Pattern fetch (API first, local cache fallback)
# ---------------------------------------------------------------------------


def _fetch_patterns_from_api(domain: str) -> Optional[List[Dict[str, Any]]]:
    """GET /api/v1/patterns from the intelligence service; None on any failure."""
    try:
        params = urllib.parse.urlencode(
            {"domain": domain, "limit": str(_API_FETCH_LIMIT), "min_confidence": "0.5"}
        )
        url = f"{INTELLIGENCE_SERVICE_URL}/api/v1/patterns?{params}"
        req = urllib.request.Request(url, method="GET")  # noqa: S310
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT_S) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
        if isinstance(body, list):
            return body
        if isinstance(body, dict) and isinstance(body.get("patterns"), list):
            return body["patterns"]
        return None
    except Exception:
        return None


def fetch_patterns(
    domain: str,
    *,
    prompt_words: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """Return patterns for *domain*: intelligence API first, local cache fallback.

    When *prompt_words* is provided the result is relevance-filtered; otherwise the
    raw domain set is returned (the sessionStart case, where no prompt exists yet).
    """
    api_patterns = _fetch_patterns_from_api(domain)
    if api_patterns is not None:
        raw = api_patterns
    else:
        cache = get_pattern_cache()
        if not cache.is_warm() or cache.is_stale():
            source = (
                LEARNED_PATTERNS_FILE
                if LEARNED_PATTERNS_FILE.exists()
                else SEED_PATTERNS_FILE
            )
            cache.warm_from_json(source)
        raw = cache.get(domain) or cache.get("general") or []
    if prompt_words:
        return filter_patterns_by_relevance(raw, domain, prompt_words)
    return list(raw)


# ---------------------------------------------------------------------------
# Prior-session summary (session-level continuity)
# ---------------------------------------------------------------------------


def load_prior_session_summary(
    current_conversation_id: str,
    *,
    sessions_root: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Most recent completed session summary, excluding the current conversation."""
    root = sessions_root if sessions_root is not None else SESSIONS_DIR
    try:
        candidates = [
            p
            for p in root.glob("*.json")
            if p.name != "current.json" and p.stem != current_conversation_id
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        data = json.loads(latest.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Markdown block builders
# ---------------------------------------------------------------------------


def _patterns_block(patterns: List[Dict[str, Any]], heading: str) -> List[str]:
    if not patterns:
        return []
    lines = [heading]
    for p in patterns[:MAX_PATTERNS]:
        # Fetched pattern text is untrusted (API/local JSON) and flows into
        # the model's additional_context — sanitize before injection (A5).
        lines.append(
            "- **[{}]** {}".format(
                sanitize_pattern_text(str(p.get("pattern_id", "?")), max_length=80),
                sanitize_pattern_text(str(p.get("description", ""))),
            )
        )
    return lines


def _delegation_block() -> str:
    return (
        "## Delegation Rule\n\n"
        "For any task requiring more than {n} tool calls, delegate as your "
        "**first action** — before any reads, writes, or shell calls:\n\n"
        "- Multiple independent subtasks → use parallel subagents\n"
        "- Single coherent task → `Agent(subagent_type='general-purpose', "
        "prompt='...', description='...')`\n\n"
        "Conversational responses are exempt."
    ).format(n=DELEGATION_THRESHOLD)


_HANDOFF_TIP = (
    "## Handoff Tip *(one-time)*\n\n"
    "For complex tasks, structure your request for better results:\n\n"
    "```\n"
    "Task:        [one sentence description]\n"
    "Scope:       [repos/files involved]\n"
    "Workflow:    [which skill to use]\n"
    "Constraints: [what NOT to do]\n"
    "Done when:   [acceptance criteria]\n"
    "```"
)


def _prior_session_block(prior_summary: Dict[str, Any]) -> str:
    lines = [
        "## Prior Session Context",
        "",
        "**Outcome:** {}  ".format(prior_summary.get("session_outcome", "unknown")),
        "**Files edited:** {}  ".format(prior_summary.get("files_edited", 0)),
    ]
    langs = prior_summary.get("languages", [])
    lines.append("**Languages:** {}  ".format(", ".join(langs) if langs else "none"))
    lines.append("**Prompts:** {}  ".format(prior_summary.get("prompts_classified", 0)))
    last_at = prior_summary.get("last_prompt_at", "")
    if last_at:
        lines.append("**Last active:** {}  ".format(last_at[:19].replace("T", " ")))
    return "\n".join(lines)


def build_session_context(
    *,
    patterns: List[Dict[str, Any]],
    prior_summary: Optional[Dict[str, Any]] = None,
    include_handoff: bool = True,
) -> str:
    """Build the ``sessionStart.additional_context`` block (session-level).

    No agent routing here — there is no prompt at session creation. Injects the
    standing delegation rule, a baseline learned-pattern set, an optional one-time
    handoff tip, and prior-session continuity when available.
    """
    header = "<!-- OmniCursor: sessionStart injection patterns={} -->".format(
        len(patterns[:MAX_PATTERNS])
    )
    sections: List[str] = [
        "## OmniCursor Session Context\n\n"
        "Agent routing is emitted per prompt for backend learning; the guidance "
        "below is session-level and refreshed after tool use."
    ]
    pattern_lines = _patterns_block(patterns, "### Learned Patterns (baseline)")
    if pattern_lines:
        sections.append("\n".join(pattern_lines))
    sections.append(_delegation_block())
    if include_handoff:
        sections.append(_HANDOFF_TIP)
    if prior_summary:
        sections.append(_prior_session_block(prior_summary))
    return header + "\n\n" + "\n\n---\n\n".join(sections)


def build_refresh_context(
    *,
    patterns: List[Dict[str, Any]],
    domain: str,
) -> str:
    """Build the ``postToolUse.additional_context`` refresh block, or '' if empty."""
    pattern_lines = _patterns_block(
        patterns, "### Learned Patterns (refreshed · {})".format(domain)
    )
    if not pattern_lines:
        return ""
    header = "<!-- OmniCursor: postToolUse refresh domain={} patterns={} -->".format(
        domain, len(patterns[:MAX_PATTERNS])
    )
    return header + "\n\n" + "\n".join(pattern_lines)

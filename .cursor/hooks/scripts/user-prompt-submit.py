"""beforeSubmitPrompt hook — classify prompt, emit for backend learning.

IMPORTANT: Cursor's ``beforeSubmitPrompt`` output schema is ``{continue, user_message}``
ONLY — it CANNOT inject context (a ``{"systemMessage": ...}`` envelope is silently
ignored). Live context injection therefore lives in the ``sessionStart`` (initial)
and ``postToolUse`` (refresh) hooks via ``additional_context``; see
``lib/context_injection.py``. This hook is now block/observe-only: it classifies the
prompt, records the relevant learned patterns for backend utilization scoring, emits
the hook event, and returns ``{"continue": true}``.

Session identity: the real ``sessionStart`` hook owns session initialization. This
hook keeps a lightweight ``_init_session`` fallback for Cursor versions predating
``sessionStart`` (idempotent), plus per-prompt correlation + timestamp bookkeeping
that stop-time aggregation reads. The same first-prompt gate doubles as the
portable daemon-ensure fallback (``lib/daemon_ensure.py``) for surfaces where
``sessionStart`` never fires.

Node contract: ``node_cursor_prompt_orchestrator``. Stdlib only; always exits 0;
never blocks Cursor.
"""

from __future__ import annotations

import datetime
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from _common import (  # noqa: E402
    SESSIONS_DIR,
    ensure_dirs,
    load_agent_configs,
    log_event,
    merge_session_json,
    read_stdin,
    write_stdout,
)
from agent_scoring import HARD_FLOOR, score_agent  # noqa: E402
from context_injection import agent_domain, fetch_patterns  # noqa: E402
from daemon_ensure import ensure_daemon  # noqa: E402
from emit_client import send_event  # noqa: E402
from prompt_pattern_selection import MAX_PATTERNS, prompt_keyword_set  # noqa: E402

DELEGATION_THRESHOLD: int = 2

# Verbs that suggest multi-deliverable, multi-step work.
_COMPLEX_VERBS = frozenset({
    "refactor", "migrate", "implement", "build", "create", "rewrite",
    "redesign", "architect", "integrate", "upgrade", "convert", "extract",
    "restructure", "overhaul", "deploy", "automate",
})

# Connective words that signal multiple sequential steps.
_MULTI_STEP_RE = re.compile(
    r"\b(then|also|additionally|after\s+that|next|finally|and\s+then|"
    r"followed\s+by|as\s+well\s+as)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Prompt classification (shared scoring engine)
# ---------------------------------------------------------------------------


def classify_prompt(
    prompt: str,
    agents: List[Dict[str, Any]],
) -> Tuple[str, float, str]:
    """Classify *prompt* against *agents* via the shared ``score_agent`` engine."""
    if not prompt or not agents:
        return ("polymorphic-agent", 0.0, "No agent matched")

    prompt_lower = prompt.lower()
    prompt_words = prompt_keyword_set(prompt)
    best_name, best_score, best_reason = "polymorphic-agent", 0.0, "No agent matched"

    for agent in agents:
        name = agent.get("name", "")
        if not name:
            continue
        sc, reason = score_agent(prompt_lower, prompt_words, agent)
        if sc >= HARD_FLOOR and sc > best_score:
            best_score, best_name, best_reason = sc, name, reason

    return (best_name, best_score, best_reason)


def _estimate_complexity(prompt: str) -> bool:
    """Return True if the prompt is likely multi-step and warrants delegation."""
    if len(prompt) < 80:
        return False
    words = set(re.findall(r"\b\w+\b", prompt.lower()))
    verb_hits = words & _COMPLEX_VERBS
    if verb_hits and _MULTI_STEP_RE.search(prompt):
        return True
    return len(verb_hits) >= 2


# ---------------------------------------------------------------------------
# Session bookkeeping (correlation + timestamps for stop-time aggregation)
# ---------------------------------------------------------------------------


def _session_dir(conversation_id: str) -> Optional[Path]:
    if not conversation_id:
        return None
    try:
        ensure_dirs()
        d = SESSIONS_DIR / conversation_id
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        return None


def _generate_correlation_id() -> str:
    return uuid.uuid4().hex[:12]


def _update_session_correlation(conversation_id: str, correlation_id: str) -> None:
    """Write the latest correlation_id into current.json so other hooks can link."""
    try:
        import json

        current = SESSIONS_DIR / "current.json"
        data: Dict[str, Any] = {}
        if current.exists():
            try:
                data = json.loads(current.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
        data["conversation_id"] = conversation_id
        data["latest_correlation_id"] = correlation_id
        current.write_text(json.dumps(data))
    except OSError:
        pass


def _init_session_fallback(conversation_id: str) -> bool:
    """Idempotent session-init fallback for Cursor versions predating sessionStart.

    Returns True only when this call performed the one-time initialization
    (i.e. this is the conversation's first prompt) — callers use it to gate
    other once-per-conversation fallbacks, like the daemon-ensure.
    """
    d = _session_dir(conversation_id)
    if not d:
        return False
    flag = d / "session_initialized"
    if flag.exists():
        return False
    try:
        flag.touch()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        merge_session_json(
            conversation_id,
            {
                "conversation_id": conversation_id,
                "started_at": now,
                "first_prompt_at": now,
                "last_prompt_at": now,
                "ci_passing": False,
            },
            sessions_root=SESSIONS_DIR,
        )
    except OSError:
        return False
    return True


def _bump_session_prompt_timestamp(conversation_id: str) -> None:
    if not conversation_id:
        return
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    merge_session_json(conversation_id, {"last_prompt_at": now}, sessions_root=SESSIONS_DIR)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _start = time.monotonic()
    correlation_id = _generate_correlation_id()

    try:
        data = read_stdin()
        prompt = data.get("prompt", "")
        conversation_id = data.get("conversation_id", "")
        generation_id = data.get("generation_id", "")

        agents = load_agent_configs()
        agent_name, score, reason = classify_prompt(prompt, agents)
        domain = agent_domain(agent_name)

        # Session bookkeeping (init fallback + correlation + timestamp).
        first_prompt = _init_session_fallback(conversation_id)
        _bump_session_prompt_timestamp(conversation_id)
        _update_session_correlation(conversation_id, correlation_id)

        # Portable daemon-ensure fallback for surfaces where sessionStart never
        # fires (older Cursor builds, CLI): once per conversation, on the first
        # prompt. Mirrors sessionStart's background-agent guard (§1a.4);
        # ensure_daemon never blocks and degrades to a no-op.
        if first_prompt and not data.get("is_background_agent", False):
            ensure_daemon()

        # Relevant patterns are recorded for backend utilization scoring — NOT
        # injected here (Cursor cannot inject at beforeSubmitPrompt; that happens
        # at sessionStart / postToolUse).
        prompt_words = prompt_keyword_set(prompt)
        patterns = fetch_patterns(domain, prompt_words=prompt_words)
        relevant_pattern_ids = [
            p.get("pattern_id", "")
            for p in patterns[:MAX_PATTERNS]
            if p.get("pattern_id")
        ]

        delegation_required = _estimate_complexity(prompt)
        hook_ms = int((time.monotonic() - _start) * 1000)

        log_event({
            "event": "prompt_classified",
            "conversation_id": conversation_id,
            "correlation_id": correlation_id,
            "generation_id": generation_id,
            "matched_agent": agent_name,
            "score": round(score, 4),
            "reason": reason,
            "patterns_injected": len(relevant_pattern_ids),
            "injected_pattern_ids": relevant_pattern_ids,
            "delegation_required": delegation_required,
            "prompt_snippet": prompt[:100],
            "hook_duration_ms": hook_ms,
        })

        send_event(
            "onex.cmd.omnicursor.cursor-hook-event.v1",
            {
                "hook": "beforeSubmitPrompt",
                "conversation_id": conversation_id,
                "correlation_id": correlation_id,
                "generation_id": generation_id,
                "matched_agent": agent_name,
                "score": round(score, 4),
                "reason": reason,
                "patterns_injected": len(relevant_pattern_ids),
                "injected_pattern_ids": relevant_pattern_ids,
                "delegation_required": delegation_required,
            },
        )
        if delegation_required:
            send_event(
                "onex.cmd.omnicursor.node-delegation-request.v1",
                {
                    "conversation_id": conversation_id,
                    "correlation_id": correlation_id,
                    "prompt_excerpt": prompt[:2000],
                    "target_orchestrator": "node_delegation_orchestrator",
                },
            )
    except Exception:
        pass

    # beforeSubmitPrompt output is block-only; allow the prompt to proceed.
    write_stdout({"continue": True})


if __name__ == "__main__":
    main()

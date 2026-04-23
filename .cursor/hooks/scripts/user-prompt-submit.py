"""beforeSubmitPrompt hook — agent routing, delegation rule, handoff nudge.

Cursor fires this hook every time the user submits a prompt. Produces a
single ``{"systemMessage": ...}`` block combining:

  1. HTML comment header — machine-readable metadata (agent, confidence,
     patterns count, delegation status, correlation ID).
  2. Agent routing + persona — best-match agent, confidence, reason, full
     agent description, approach instructions, recommended skill, and
     relevance-filtered learned patterns.
  3. Delegation rule — hard behavioral constraint when the prompt is
     estimated to require delegation; advisory otherwise.
  4. Handoff nudge — once per session, for complex unstructured requests.

Session identity
  - On the FIRST prompt of a conversation, ``_init_session`` writes
    ``~/.omnicursor/sessions/current.json`` and a ``session_initialized``
    flag so Events 2–4 can identify the active session.
  - A per-prompt ``correlation_id`` threads through the log event and the
    injected header so all hook calls within a single prompt can be traced.

Always exits 0. Always emits valid JSON.

Ported and extended from omniclaude:
  - user-prompt-submit.sh           (routing + pattern injection)
  - user-prompt-delegation-rule.sh  (counter reset + delegation rule)
  - user_prompt_structured_handoff_nudge.sh  (once-per-session nudge)

Learned-pattern relevance filtering is imported from
``lib/prompt_pattern_selection.py`` (shared with ``omnicursor.prompt_pattern_read``;
see ``docs/dev/OMNICLAUDE_TO_CURSOR_PORT.md``).
"""

from __future__ import annotations

import datetime
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from _common import (
    LEARNED_PATTERNS_FILE,
    SESSIONS_DIR,
    ensure_dirs,
    load_agent_configs,
    log_event,
    merge_session_json,
    read_stdin,
    write_context,
)
from agent_scoring import HARD_FLOOR, score_agent
from emit_client import send_event
from pattern_loader import get_pattern_cache
from prompt_pattern_selection import (
    MAX_PATTERNS,
    filter_patterns_by_relevance,
    prompt_keyword_set,
    score_pattern_relevance,
)

# Private names kept for hook self-tests (tests/test_suite_event1_prompt.py).
_score_pattern_relevance = score_pattern_relevance
_filter_patterns_by_relevance = filter_patterns_by_relevance


# ---------------------------------------------------------------------------
# Routing constants
# ---------------------------------------------------------------------------

# HARD_FLOOR imported from agent_scoring (single source of truth).
DELEGATION_THRESHOLD: int = 2

# Structured prompt field markers — if present, prompt is already structured.
_STRUCTURE_MARKERS = re.compile(
    r"(^|\n)\s*(Task|Scope|Constraints|Done when|Workflow|Requirements|Files)\s*:",
    re.IGNORECASE,
)

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
# Prompt classification — multi-strategy scoring
# ---------------------------------------------------------------------------


def classify_prompt(
    prompt: str, agents: List[Dict[str, Any]],
) -> Tuple[str, float, str]:
    """Classify *prompt* against *agents* using the shared scoring engine.

    Delegates to ``agent_scoring.score_agent`` — the single source of truth
    shared with on_prompt.py and src/omnicursor/agents.py.
    """
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


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------


def _session_dir(conversation_id: str) -> Optional[Path]:
    """Return the session state directory, creating it if needed."""
    if not conversation_id:
        return None
    try:
        ensure_dirs()
        d = SESSIONS_DIR / conversation_id
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Session identity — fake SessionStart
# ---------------------------------------------------------------------------


def _generate_correlation_id() -> str:
    """Return a short unique ID for this specific prompt/hook invocation."""
    return uuid.uuid4().hex[:12]


def _update_session_correlation(conversation_id: str, correlation_id: str) -> None:
    """Write the latest correlation_id into current.json on every prompt.

    Events 2–4 read this value to link their log entries back to the prompt
    that triggered them, giving events.jsonl a coherent per-prompt trace.
    Preserves all existing keys in current.json (e.g. started_at).
    """
    try:
        current = SESSIONS_DIR / "current.json"
        data: Dict[str, Any] = {}
        if current.exists():
            try:
                data = json.loads(current.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        data["conversation_id"] = conversation_id
        data["latest_correlation_id"] = correlation_id
        current.write_text(json.dumps(data))
    except OSError:
        pass


# Fake SessionStart (Cursor has no session-open hook): first beforeSubmitPrompt per
# Cursor conversation_id. Trigger rule: ~/.omnicursor/sessions/<conversation_id>/
# exists but session_initialized is absent — we touch the flag and write state once.
# Same conversation_id reuses the session until Cursor starts a new chat (new id).
def _init_session(conversation_id: str) -> bool:
    """On the FIRST beforeSubmitPrompt call for a conversation:
    - Touch a ``session_initialized`` flag so subsequent calls are no-ops.
    - Write ``~/.omnicursor/sessions/current.json`` so Events 2–4 can read
      the active conversation_id without receiving it from Cursor directly.
    - Create / merge ``~/.omnicursor/sessions/<conversation_id>.json`` (session state).

    Returns True if this invocation performed first-prompt initialization.
    Idempotent: subsequent calls with the same conversation_id return False.
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
        current = SESSIONS_DIR / "current.json"
        current.write_text(json.dumps({
            "conversation_id": conversation_id,
            "started_at": now,
        }))
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
        return True
    except OSError:
        return False


def _bump_session_prompt_timestamp(conversation_id: str) -> None:
    """Update last_prompt_at for recurring prompts in the same conversation."""
    if not conversation_id:
        return
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    merge_session_json(conversation_id, {"last_prompt_at": now}, sessions_root=SESSIONS_DIR)


# ---------------------------------------------------------------------------
# Per-turn state reset (delegation rule)
# ---------------------------------------------------------------------------


def reset_turn_state(conversation_id: str) -> None:
    """Reset per-turn counters at the start of each prompt.

    Clears write/read counts and the delegation flag so each prompt
    starts with a clean slate.
    """
    d = _session_dir(conversation_id)
    if not d:
        return
    try:
        (d / "write_count").write_text("0")
        (d / "read_count").write_text("0")
        (d / "delegated").unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Handoff nudge (once per session)
# ---------------------------------------------------------------------------


def _is_complex_unstructured(prompt: str) -> bool:
    """Return True if prompt is long, unstructured, and not a skill invocation."""
    if len(prompt) < 50:
        return False
    if prompt.lstrip().startswith("/"):
        return False
    if _STRUCTURE_MARKERS.search(prompt):
        return False
    return True


def should_nudge(conversation_id: str) -> bool:
    d = _session_dir(conversation_id)
    if not d:
        return False
    return not (d / "handoff_nudge_fired").exists()


def mark_nudge_fired(conversation_id: str) -> None:
    d = _session_dir(conversation_id)
    if not d:
        return
    try:
        (d / "handoff_nudge_fired").touch()
    except OSError:
        pass


# Pattern relevance: shared stdlib implementation in ``lib/prompt_pattern_selection.py``.

# ---------------------------------------------------------------------------
# Complexity estimator — gates hard delegation enforcement
# ---------------------------------------------------------------------------


def _estimate_complexity(prompt: str) -> bool:
    """Return True if the prompt is likely multi-step and requires delegation.

    Fires when the prompt is >= 80 characters AND either:
      - Contains a complex verb (refactor, migrate, …) AND a multi-step
        connective (then, additionally, …), OR
      - Contains 2 or more distinct complex verbs (implies multiple
        deliverables in a single request).
    """
    if len(prompt) < 80:
        return False
    words = set(re.findall(r"\b\w+\b", prompt.lower()))
    verb_hits = words & _COMPLEX_VERBS
    if verb_hits and _MULTI_STEP_RE.search(prompt):
        return True
    if len(verb_hits) >= 2:
        return True
    return False


# ---------------------------------------------------------------------------
# Context block assembly
# ---------------------------------------------------------------------------


def _agent_domain(agent_name: str) -> str:
    domain = agent_name.lower()
    for prefix in ("agent-", "omnicursor-"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
            break
    return domain.replace("-", "_")


def build_context(
    agent_name: str,
    score: float,
    reason: str,
    patterns: List[Dict[str, Any]],
    prompt: str,
    conversation_id: str,
    agent_config: Optional[Dict[str, Any]] = None,
    correlation_id: str = "",
    delegation_required: bool = False,
) -> str:
    """Build the systemMessage injected by Cursor before the model responds.

    Parameters
    ----------
    agent_name:          Selected agent's name (or 'polymorphic-agent').
    score:               Routing confidence score (0.0–1.0).
    reason:              Human-readable routing reason.
    patterns:            Already-filtered learned patterns to inject.
    prompt:              Raw user prompt text (used for nudge logic).
    conversation_id:     Cursor-provided conversation ID (may be empty).
    agent_config:        Full agent JSON dict for persona injection.
    correlation_id:      Per-prompt trace ID written into the header.
    delegation_required: When True, injection uses imperative language.
    """
    sections: List[str] = []

    # --- HTML comment header (machine-readable, not shown to user) ---
    delegation_label = "required" if delegation_required else "advisory"
    header_lines = [
        "<!-- OmniCursor: agent={} confidence={:.2f} -->".format(agent_name, score),
        "<!-- OmniCursor: patterns={} injected domain={} -->".format(
            len(patterns[:MAX_PATTERNS]), _agent_domain(agent_name),
        ),
        "<!-- OmniCursor: delegation={} -->".format(delegation_label),
    ]
    if correlation_id:
        header_lines.append(
            "<!-- OmniCursor: correlation={} -->".format(correlation_id)
        )

    # --- Section 1: Agent routing + persona ---
    routing = [
        "## OmniCursor Agent Routing",
        "",
        "**Agent:** `{}`  ".format(agent_name),
        "**Confidence:** {:.2f}  ".format(score),
        "**Reason:** {}".format(reason),
    ]
    cfg = agent_config or {}
    desc: str = cfg.get("description", "")
    instructions: List[str] = cfg.get("instructions") or []
    skill: Optional[str] = cfg.get("recommended_skill")

    if desc:
        routing += ["", "**Role:** {}".format(desc)]
    if instructions:
        routing += ["", "**Approach:**"]
        for instr in instructions:
            routing.append("- {}".format(instr))
    if skill:
        routing += ["", "**Recommended skill:** `/{}`".format(skill)]
    if patterns:
        routing += ["", "### Learned Patterns"]
        for p in patterns[:MAX_PATTERNS]:
            routing.append("- **[{}]** {}".format(
                p.get("pattern_id", "?"), p.get("description", ""),
            ))
    sections.append("\n".join(routing))

    # --- Section 2: Delegation rule ---
    if delegation_required:
        delegation = (
            "## Delegation Rule\n\n"
            "**This task requires delegation.** Before any reads, writes, or "
            "tool calls, you **MUST** delegate to a subagent as your first "
            "action:\n\n"
            "- Multiple independent subtasks → use parallel subagents\n"
            "- Single coherent task → `Agent(subagent_type='general-purpose', "
            "prompt='...', description='...')`\n\n"
            "Do not begin work inline — delegate first, then monitor."
        )
    else:
        delegation = (
            "## Delegation Rule\n\n"
            "For any task requiring more than {n} tool calls, delegate as your "
            "**first action** — before any reads, writes, or shell calls:\n\n"
            "- Multiple independent subtasks → use parallel subagents\n"
            "- Single coherent task → `Agent(subagent_type='general-purpose', "
            "prompt='...', description='...')`\n\n"
            "Conversational responses are exempt."
        ).format(n=DELEGATION_THRESHOLD)
    sections.append(delegation)

    # --- Section 3: Handoff nudge (once per session) ---
    if _is_complex_unstructured(prompt) and should_nudge(conversation_id):
        mark_nudge_fired(conversation_id)
        nudge = (
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
        sections.append(nudge)

    body = "\n\n---\n\n".join(sections)
    header = "\n".join(header_lines)
    return header + "\n\n" + body


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _start = time.monotonic()

    agent_name = "polymorphic-agent"
    score = 0.0
    reason = "No agent matched"
    patterns: List[Dict[str, Any]] = []
    prompt = ""
    conversation_id = ""
    agent_config: Dict[str, Any] = {}
    correlation_id = _generate_correlation_id()
    delegation_required = False

    try:
        data = read_stdin()
        prompt = data.get("prompt", "")
        conversation_id = data.get("conversation_id", "")
        generation_id = data.get("generation_id", "")

        agents = load_agent_configs()
        agent_name, score, reason = classify_prompt(prompt, agents)

        # Retrieve full agent config for persona injection.
        agent_config = next(
            (a for a in agents if a.get("name") == agent_name), {}
        )

        # Session identity: write current.json + sessions/<id>.json on first prompt,
        # then update the correlation_id so Events 2–4 can read it.
        first_prompt = _init_session(conversation_id)
        if not first_prompt:
            _bump_session_prompt_timestamp(conversation_id)
        _update_session_correlation(conversation_id, correlation_id)
        reset_turn_state(conversation_id)

        # Pattern loading with relevance filtering.
        cache = get_pattern_cache()
        if not cache.is_warm() or cache.is_stale():
            cache.warm_from_json(LEARNED_PATTERNS_FILE)
        domain = _agent_domain(agent_name)
        raw = cache.get(domain) or cache.get("general") or []
        prompt_words_set = prompt_keyword_set(prompt)
        patterns = filter_patterns_by_relevance(raw, domain, prompt_words_set)

        # Complexity estimation gates delegation enforcement framing.
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
            "patterns_injected": len(patterns),
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
                "patterns_injected": len(patterns),
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

    write_context(build_context(
        agent_name, score, reason, patterns, prompt, conversation_id,
        agent_config=agent_config,
        correlation_id=correlation_id,
        delegation_required=delegation_required,
    ))


if __name__ == "__main__":
    main()

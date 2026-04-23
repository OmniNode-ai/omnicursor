"""beforeSubmitPrompt hook — classify prompt and emit enrichment payload.

Node contract: ``node_cursor_prompt_orchestrator``
(``src/omnicursor/nodes/node_cursor_prompt_orchestrator/contract.yaml``).

Classifies the user prompt against agent configs, selects the best-match
agent, and writes a ``{"systemMessage": ...}`` JSON payload to stdout
containing the agent name, confidence score, and routing reason.

Falls back to ``polymorphic-agent`` with score 0.0 when no agent matches.
Always exits 0 and always emits valid JSON.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# _common and pattern_loader live in the same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Shared lib modules (agent_scoring, prompt_pattern_selection, …) live in lib/.
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from _common import (
    LEARNED_PATTERNS_FILE,
    load_agent_configs,
    log_event,
    read_stdin,
    write_stdout,
)
from agent_scoring import HARD_FLOOR, extract_keywords, score_agent
from pattern_loader import get_pattern_cache


# ---------------------------------------------------------------------------
# Prompt classification
# ---------------------------------------------------------------------------


def classify_prompt(
    prompt: str, agents: List[Dict[str, Any]],
) -> Tuple[str, float, str]:
    """Return ``(agent_name, score, reason)``.

    Scoring is delegated to ``agent_scoring.score_agent`` — the single
    source of truth shared with scripts/user-prompt-submit.py and
    src/omnicursor/agents.py.

    Only agents scoring at or above ``HARD_FLOOR`` are considered.
    Falls back to ``('polymorphic-agent', 0.0, 'No agent matched')``.
    """
    if not prompt or not agents:
        return ("polymorphic-agent", 0.0, "No agent matched")

    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt))
    best_name = "polymorphic-agent"
    best_score = 0.0
    best_reason = "No agent matched"

    for agent in agents:
        name = agent.get("name", "")
        if not name:
            continue
        sc, reason = score_agent(prompt_lower, prompt_words, agent)
        if sc >= HARD_FLOOR and sc > best_score:
            best_score = sc
            best_name = name
            best_reason = reason

    return (best_name, best_score, best_reason)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


MAX_PATTERNS_TO_INJECT = 5


def _format_system_message(
    agent_name: str,
    score: float,
    reason: str,
    patterns: List[Dict[str, Any]],
) -> str:
    """Build the enrichment block injected via ``systemMessage``."""
    lines = [
        "<!-- OmniCursor Agent: {name} (confidence: {score:.2f}) -->".format(
            name=agent_name, score=score,
        ),
        "<!-- Routing reason: {reason} -->".format(reason=reason),
    ]

    if patterns:
        lines.append("")
        lines.append("<!-- Learned Patterns (from previous sessions): -->")
        for p in patterns[:MAX_PATTERNS_TO_INJECT]:
            pid = p.get("pattern_id", "?")
            desc = p.get("description", "")
            lines.append("<!-- - [{pid}] {desc} -->".format(pid=pid, desc=desc))

    return "\n".join(lines)


def _agent_domain(agent_name: str) -> str:
    """Derive a pattern-cache domain key from the agent name.

    Strips common prefixes and normalises hyphens to underscores so that
    an agent named ``debug-intelligence`` maps to domain ``debug_intelligence``.
    """
    domain = agent_name.lower()
    for prefix in ("agent-", "omnicursor-"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
            break
    return domain.replace("-", "_")


def main() -> None:
    # Defaults — used if anything goes wrong so we always emit valid JSON.
    agent_name = "polymorphic-agent"
    score = 0.0
    reason = "No agent matched"
    patterns: List[Dict[str, Any]] = []

    try:
        data = read_stdin()
        prompt = data.get("prompt", "")
        conversation_id = data.get("conversation_id", "")
        generation_id = data.get("generation_id", "")

        agents = load_agent_configs()
        agent_name, score, reason = classify_prompt(prompt, agents)

        # --- Pattern loading (Task 2) ---
        cache = get_pattern_cache()
        if not cache.is_warm() or cache.is_stale():
            cache.warm_from_json(LEARNED_PATTERNS_FILE)

        domain = _agent_domain(agent_name)
        patterns = cache.get(domain)
        # Fall back to "general" if nothing domain-specific.
        if not patterns:
            patterns = cache.get("general")

        log_event(
            {
                "event": "prompt_classified",
                "conversation_id": conversation_id,
                "generation_id": generation_id,
                "matched_agent": agent_name,
                "score": round(score, 4),
                "reason": reason,
                "patterns_injected": len(patterns[:MAX_PATTERNS_TO_INJECT]),
                "prompt_snippet": prompt[:100],
            }
        )
    except Exception:
        pass

    write_stdout({
        "systemMessage": _format_system_message(agent_name, score, reason, patterns),
    })


if __name__ == "__main__":
    main()

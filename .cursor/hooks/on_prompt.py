"""beforeSubmitPrompt hook — classify prompt and log. Informational only.

Cursor ignores stdout from this hook. We classify the prompt against agent
configs for observability, then write ``{}`` and exit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure _common is importable from the same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import load_agent_configs, log_event, read_stdin, write_stdout


# ---------------------------------------------------------------------------
# Prompt classification
# ---------------------------------------------------------------------------


def _score_agent(prompt_lower: str, agent: Dict[str, Any]) -> float:
    """Score a single agent config against the lowered prompt."""
    activation = agent.get("activation_patterns", {})
    explicit: List[str] = activation.get("explicit_triggers", [])
    context: List[str] = activation.get("context_triggers", [])

    max_points = 2 * len(explicit) + len(context)
    if max_points == 0:
        return 0.0

    points = 0
    for trigger in explicit:
        if trigger.lower() in prompt_lower:
            points += 2
    for trigger in context:
        if trigger.lower() in prompt_lower:
            points += 1

    return points / max_points


def classify_prompt(prompt: str, agents: List[Dict[str, Any]]) -> Tuple[str, float]:
    """Return (agent_name, score). Falls back to ('polymorphic-agent', 0.0)."""
    if not prompt or not agents:
        return ("polymorphic-agent", 0.0)

    prompt_lower = prompt.lower()
    best_name = "polymorphic-agent"
    best_score = 0.0

    for agent in agents:
        name = agent.get("name", "")
        if not name:
            continue
        score = _score_agent(prompt_lower, agent)
        if score > best_score:
            best_score = score
            best_name = name

    return (best_name, best_score)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        data = read_stdin()
        prompt = data.get("prompt", "")
        conversation_id = data.get("conversation_id", "")
        generation_id = data.get("generation_id", "")

        agents = load_agent_configs()
        matched_agent, score = classify_prompt(prompt, agents)

        log_event(
            {
                "event": "prompt_classified",
                "conversation_id": conversation_id,
                "generation_id": generation_id,
                "matched_agent": matched_agent,
                "score": round(score, 4),
                "prompt_snippet": prompt[:100],
            }
        )
    except Exception:
        pass

    write_stdout({})


if __name__ == "__main__":
    main()

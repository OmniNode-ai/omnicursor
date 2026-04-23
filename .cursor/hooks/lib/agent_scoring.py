# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Canonical agent-routing scoring engine (stdlib only).

Single source of truth for the three-strategy scoring algorithm shared by:
  - .cursor/hooks/on_prompt.py               (test-facing hook)
  - .cursor/hooks/scripts/user-prompt-submit.py  (Cursor runtime hook)
  - src/omnicursor/agents.py                 (Python library, via importlib bridge)

The Python library must not import this file directly (that would make
omnicursor a hook dependency). Instead it loads this module by path using
importlib, exactly as src/omnicursor/prompt_pattern_read.py does for
prompt_pattern_selection.py.

See docs/dev/ROUTING_DEDUPLICATION.md.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

HARD_FLOOR: float = 0.55

# Identical to prompt_pattern_selection.STOPWORDS.
# Kept here to avoid a cross-module dependency between lib/ files.
STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "i", "in", "is", "it", "my", "not", "of", "on",
    "or", "the", "this", "that", "to", "was", "we", "with", "you",
})


def extract_keywords(text: str) -> list[str]:
    """Tokenize *text* into significant lowercase words (stopwords excluded)."""
    return [
        w for w in re.findall(r"\b\w+\b", text.lower())
        if w not in STOPWORDS and len(w) > 2
    ]


def fuzzy_threshold(trigger: str) -> float:
    """Length-aware similarity threshold: shorter triggers require higher ratio."""
    n = len(trigger)
    if n <= 6:
        return 0.85
    if n <= 10:
        return 0.78
    return 0.72


def score_agent(
    prompt_lower: str,
    prompt_words: set[str],
    agent: dict[str, Any],
) -> tuple[float, str]:
    """Multi-strategy scoring for a single agent config dict.

    Strategies (evaluated in order; best score wins):
      1. Exact substring on explicit_triggers   -> 0.95
      2. Exact substring on context_triggers    -> 0.80
      3. Fuzzy SequenceMatcher on explicit_triggers (length-aware threshold)
      4. Keyword overlap on activation_keywords -> scaled 0.55-0.85

    Returns (score, reason). score 0.0 means no match.
    """
    activation = agent.get("activation_patterns", {})
    explicit: list[str] = activation.get("explicit_triggers", [])
    context: list[str] = activation.get("context_triggers", [])

    best_score = 0.0
    best_reason = ""

    for trigger in explicit:
        if trigger.lower() in prompt_lower and 0.95 > best_score:
            best_score = 0.95
            best_reason = "Exact trigger: '{}'".format(trigger)

    for trigger in context:
        if trigger.lower() in prompt_lower and 0.80 > best_score:
            best_score = 0.80
            best_reason = "Context trigger: '{}'".format(trigger)

    if best_score < 0.90:
        words_in_prompt = re.findall(r"\b\w+\b", prompt_lower)
        for trigger in explicit:
            trigger_lower = trigger.lower()
            threshold = fuzzy_threshold(trigger_lower)
            for word in words_in_prompt:
                ratio = SequenceMatcher(None, trigger_lower, word).ratio()
                if ratio >= threshold and ratio > best_score:
                    best_score = ratio
                    best_reason = "Fuzzy match: '{}' ({:.0%})".format(trigger, ratio)

    if best_score < 0.70:
        keywords_raw: list[str] = activation.get("activation_keywords", [])
        if not keywords_raw:
            keywords_raw = [w for t in explicit for w in t.lower().split()]
        keyword_set = {k.lower() for k in keywords_raw if len(k) > 2} - STOPWORDS
        if keyword_set:
            overlap = prompt_words & keyword_set
            if len(overlap) >= 2:
                scaled = 0.55 + (len(overlap) / len(keyword_set) * 0.30)
                if scaled > best_score:
                    best_score = scaled
                    best_reason = "Keywords: {{{}}}".format(", ".join(sorted(overlap)))

    return (best_score, best_reason)

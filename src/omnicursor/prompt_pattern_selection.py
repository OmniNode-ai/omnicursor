# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Learned-pattern relevance filtering — canonical source of truth.

Shared by:
  - src/omnicursor/nodes/node_cursor_pattern_injection_compute/handlers/
  - src/omnicursor/prompt_pattern_read.py  (re-exports for backwards compat)
  - .cursor/hooks/lib/prompt_pattern_selection.py  (thin shim re-exports from here)

Stdlib-only — no pip dependencies.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "i", "in", "is", "it", "my", "not", "of", "on",
    "or", "the", "this", "that", "to", "was", "we", "with", "you",
})

PATTERN_RELEVANCE_THRESHOLD: float = 0.7
MAX_PATTERNS: int = 5


def extract_keywords(text: str) -> list[str]:
    """Tokenize prompt into significant lowercase words (stopwords excluded)."""
    return [
        w for w in re.findall(r"\b\w+\b", text.lower())
        if w not in STOPWORDS and len(w) > 2
    ]


def prompt_keyword_set(prompt: str) -> set[str]:
    return set(extract_keywords(prompt))


def score_pattern_relevance(
    pattern: dict[str, Any],
    domain: str,
    prompt_words: set[str],
) -> float:
    """Score a learned pattern's relevance to the current prompt and domain."""
    p_domain = pattern.get("domain", "general")
    if p_domain == domain:
        base = 1.0
    elif p_domain == "general":
        base = 0.6
    else:
        base = 0.3

    desc = pattern.get("description", "")
    desc_words = (
        {w for w in re.findall(r"\b\w+\b", str(desc).lower()) if len(w) > 2}
        - STOPWORDS
    )
    if desc_words and prompt_words:
        overlap_ratio = len(prompt_words & desc_words) / len(desc_words)
        boost = overlap_ratio * 0.4
    else:
        boost = 0.0

    return min(1.0, base + boost)


def filter_patterns_by_relevance(
    patterns: Iterable[dict[str, Any]],
    domain: str,
    prompt_words: set[str],
    *,
    threshold: float = PATTERN_RELEVANCE_THRESHOLD,
    limit: int = MAX_PATTERNS,
) -> list[dict[str, Any]]:
    """Filter to threshold, rank by score, cap at limit."""
    scored = [(p, score_pattern_relevance(p, domain, prompt_words)) for p in patterns]
    filtered = [(p, s) for p, s in scored if s >= threshold]
    filtered.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in filtered[:limit]]


def load_pattern_dicts_from_file(path: Path) -> list[dict[str, Any]]:
    """Load patterns list from learned_patterns.json shape."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    patterns = data.get("patterns", [])
    if not isinstance(patterns, list):
        return []
    return [p for p in patterns if isinstance(p, dict)]


def select_patterns_for_prompt(
    path: Path,
    *,
    prompt: str,
    domain: str = "general",
) -> list[dict[str, Any]]:
    """Load from path and return relevance-ranked patterns for prompt."""
    raw = load_pattern_dicts_from_file(path)
    words = prompt_keyword_set(prompt)
    return filter_patterns_by_relevance(raw, domain, words)

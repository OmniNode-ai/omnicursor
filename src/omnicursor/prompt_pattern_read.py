# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Learned-pattern read API for tests and ``node_cursor_pattern_injection_compute``.

Re-exports from ``omnicursor.prompt_pattern_selection`` (the canonical source).
"""

from __future__ import annotations

from omnicursor.prompt_pattern_selection import (
    MAX_PATTERNS,
    PATTERN_RELEVANCE_THRESHOLD,
    STOPWORDS,
    extract_keywords,
    filter_patterns_by_relevance,
    load_pattern_dicts_from_file,
    prompt_keyword_set,
    score_pattern_relevance,
    select_patterns_for_prompt,
)

__all__ = [
    "MAX_PATTERNS",
    "PATTERN_RELEVANCE_THRESHOLD",
    "STOPWORDS",
    "extract_keywords",
    "filter_patterns_by_relevance",
    "load_pattern_dicts_from_file",
    "prompt_keyword_set",
    "score_pattern_relevance",
    "select_patterns_for_prompt",
]

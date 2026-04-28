# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Thin shim — re-exports from src/omnicursor/prompt_pattern_selection.py (canonical).

Hook scripts import this file via sys.path (lib/ is on sys.path). This shim
adds src/ to sys.path so omnicursor.prompt_pattern_selection can be imported
without venv activation.
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo = Path(__file__).resolve().parents[3]
_src = str(_repo / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from omnicursor.prompt_pattern_selection import (  # noqa: E402
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

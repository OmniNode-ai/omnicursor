# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Thin shim — re-exports from src/omnicursor/scoring.py (the canonical source).

Hook scripts import this file directly via sys.path (lib/ is on sys.path).
This shim adds src/ to sys.path so omnicursor.scoring can be imported without
making hooks depend on a venv.

See docs/dev/ROUTING_DEDUPLICATION.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ so hooks can import omnicursor.* without venv activation.
_repo = Path(__file__).resolve().parents[3]
_src = str(_repo / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from omnicursor.scoring import (  # noqa: E402
    HARD_FLOOR,
    STOPWORDS,
    extract_keywords,
    fuzzy_threshold,
    score_agent,
)

__all__ = [
    "HARD_FLOOR",
    "STOPWORDS",
    "extract_keywords",
    "fuzzy_threshold",
    "score_agent",
]

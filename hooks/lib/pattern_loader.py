# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Thin shim — re-exports PatternCache from src/omnicursor/pattern_cache.py (canonical)."""

from __future__ import annotations

import sys
from pathlib import Path

_src = str(Path(__file__).resolve().parents[2] / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from omnicursor.pattern_cache import PatternCache, get_pattern_cache  # noqa: E402, F401

__all__ = ["PatternCache", "get_pattern_cache"]

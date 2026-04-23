# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Learned-pattern read API for tests and ``node_cursor_pattern_injection_compute``.

The **canonical implementation** is stdlib-only and lives next to the Cursor hook
library: ``.cursor/hooks/lib/prompt_pattern_selection.py``. Hooks import that file
directly; this module loads it by path so ``omnicursor`` never becomes a hook
dependency, while ``pytest`` and node handlers still ``import omnicursor``.

See ``docs/dev/OMNICLAUDE_TO_CURSOR_PORT.md``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _selection_module() -> ModuleType:
    repo = Path(__file__).resolve().parents[2]
    path = repo / ".cursor" / "hooks" / "lib" / "prompt_pattern_selection.py"
    if not path.is_file():
        msg = (
            "OmniCursor checkout layout required: expected "
            f"{path} (pattern selection lives with hooks; see docs)."
        )
        raise RuntimeError(msg)
    name = "_omnicursor_hook_prompt_pattern_selection"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        msg = f"Cannot load pattern selection from {path}"
        raise RuntimeError(msg)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ps = _selection_module()

# Re-export for tests, node handlers, and external callers.
PATTERN_RELEVANCE_THRESHOLD = _ps.PATTERN_RELEVANCE_THRESHOLD
MAX_PATTERNS = _ps.MAX_PATTERNS
STOPWORDS = _ps.STOPWORDS
extract_keywords = _ps.extract_keywords
prompt_keyword_set = _ps.prompt_keyword_set
score_pattern_relevance = _ps.score_pattern_relevance
filter_patterns_by_relevance = _ps.filter_patterns_by_relevance
load_pattern_dicts_from_file = _ps.load_pattern_dicts_from_file
select_patterns_for_prompt = _ps.select_patterns_for_prompt

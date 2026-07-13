"""Tests for read-side learned-pattern selection (library source for pattern node)."""

from __future__ import annotations

import json
from pathlib import Path

from omnicursor.prompt_pattern_read import (
    MAX_PATTERNS,
    PATTERN_RELEVANCE_THRESHOLD,
    filter_patterns_by_relevance,
    load_pattern_dicts_from_file,
    prompt_keyword_set,
    score_pattern_relevance,
    select_patterns_for_prompt,
)


def test_score_pattern_relevance_domain_match() -> None:
    p = {"domain": "testing", "description": "run pytest for regressions"}
    words = prompt_keyword_set("how do I run pytest for this repo")
    s = score_pattern_relevance(p, "testing", words)
    assert s >= 1.0


def test_filter_patterns_respects_threshold(tmp_path: Path) -> None:
    path = tmp_path / "learned_patterns.json"
    path.write_text(
        json.dumps(
            {
                "patterns": [
                    {"domain": "general", "description": "x", "pattern_id": "a"},
                    {
                        "domain": "hooks",
                        "description": "shell guard blocks dangerous rm patterns",
                        "pattern_id": "b",
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    prompt = "tell me about shell guard and rm safety in hooks"
    words = prompt_keyword_set(prompt)
    selected = select_patterns_for_prompt(path, prompt=prompt, domain="hooks")
    assert all(isinstance(x, dict) for x in selected)
    assert len(selected) <= MAX_PATTERNS
    for p in selected:
        assert score_pattern_relevance(p, "hooks", words) >= PATTERN_RELEVANCE_THRESHOLD


def test_load_pattern_dicts_missing_file(tmp_path: Path) -> None:
    assert load_pattern_dicts_from_file(tmp_path / "nope.json") == []


def test_filter_patterns_empty() -> None:
    assert filter_patterns_by_relevance([], "general", set()) == []

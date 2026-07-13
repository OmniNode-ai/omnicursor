# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

import json

import pytest

from omnicursor.nodes.node_cursor_pattern_injection_compute.models.input import (
    PatternInjectionInput,
)
from omnicursor.nodes.node_cursor_pattern_injection_compute.models.output import (
    PatternInjectionOutput,
)
from omnicursor.nodes.node_cursor_pattern_injection_compute.handlers.handle_pattern_inject import (
    handle_pattern_inject,
)
from omnicursor.nodes.node_cursor_pattern_injection_compute.node import run


@pytest.fixture
def empty_patterns_file(tmp_path):
    f = tmp_path / "learned_patterns.json"
    f.write_text(json.dumps({"patterns": []}))
    return f


@pytest.fixture
def patterns_file_with_data(tmp_path):
    f = tmp_path / "learned_patterns.json"
    f.write_text(
        json.dumps(
            {
                "patterns": [
                    {"pattern": "debug", "domain": "debugging", "weight": 0.9},
                    {"pattern": "fix bug", "domain": "debugging", "weight": 0.8},
                ]
            }
        )
    )
    return f


class TestPatternInjectionModels:
    def test_input_requires_prompt_and_file(self):
        with pytest.raises(Exception):
            PatternInjectionInput(prompt="test")

    def test_input_domain_defaults_to_general(self, empty_patterns_file):
        i = PatternInjectionInput(prompt="test", patterns_file=empty_patterns_file)
        assert i.domain == "general"

    def test_output_has_patterns_and_count(self):
        o = PatternInjectionOutput(patterns=[], count=0)
        assert o.count == 0
        assert o.patterns == []


class TestHandlerPatternInject:
    def test_empty_file_returns_empty_patterns(self, empty_patterns_file):
        result = handle_pattern_inject(
            PatternInjectionInput(
                prompt="debug this", patterns_file=empty_patterns_file
            )
        )
        assert isinstance(result, PatternInjectionOutput)
        assert result.count == len(result.patterns)

    def test_output_count_matches_patterns_length(self, empty_patterns_file):
        result = handle_pattern_inject(
            PatternInjectionInput(prompt="anything", patterns_file=empty_patterns_file)
        )
        assert result.count == len(result.patterns)


class TestNodeRunAPI:
    def test_run_returns_output(self, empty_patterns_file):
        result = run("test prompt", empty_patterns_file)
        assert isinstance(result, PatternInjectionOutput)

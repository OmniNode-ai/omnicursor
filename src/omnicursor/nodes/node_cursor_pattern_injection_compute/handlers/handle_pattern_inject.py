# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from omnicursor.prompt_pattern_read import select_patterns_for_prompt
from omnicursor.nodes.node_cursor_pattern_injection_compute.models.input import PatternInjectionInput
from omnicursor.nodes.node_cursor_pattern_injection_compute.models.output import PatternInjectionOutput


def handle_pattern_inject(input: PatternInjectionInput) -> PatternInjectionOutput:
    patterns = select_patterns_for_prompt(
        input.patterns_file,
        prompt=input.prompt,
        domain=input.domain,
    )
    return PatternInjectionOutput(patterns=patterns, count=len(patterns))

# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pathlib import Path

from omnicursor.nodes.node_cursor_pattern_injection_compute.handlers.handle_pattern_inject import (
    handle_pattern_inject,
)
from omnicursor.nodes.node_cursor_pattern_injection_compute.models.input import (
    PatternInjectionInput,
)
from omnicursor.nodes.node_cursor_pattern_injection_compute.models.output import (
    PatternInjectionOutput,
)

CONTRACT_NAME = "node_cursor_pattern_injection_compute"


def run(
    prompt: str, patterns_file: Path, domain: str = "general"
) -> PatternInjectionOutput:
    return handle_pattern_inject(
        PatternInjectionInput(prompt=prompt, patterns_file=patterns_file, domain=domain)
    )

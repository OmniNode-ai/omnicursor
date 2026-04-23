"""Node ``handler.py`` bindings align with ``contract.yaml`` + ``hooks.json``."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from omnicursor.node_contracts import load_all_contracts

_HANDLER_MODULES = (
    "omnicursor.nodes.node_cursor_prompt_orchestrator.handler",
    "omnicursor.nodes.node_cursor_shell_guard_effect.handler",
    "omnicursor.nodes.node_cursor_file_edit_effect.handler",
    "omnicursor.nodes.node_cursor_session_outcome_orchestrator.handler",
    "omnicursor.nodes.node_cursor_pattern_injection_compute.handler",
)


@pytest.mark.parametrize("module_path", _HANDLER_MODULES)
def test_handler_hook_binding_matches_contract(module_path: str) -> None:
    mod = importlib.import_module(module_path)
    binding = mod.hook_binding()
    name = mod.CONTRACT_NAME
    contracts = {c.name: c for c in load_all_contracts()}
    c = contracts[name]
    assert binding["hook_event"] == c.cursor_native.hook_event
    assert binding["hooks_json_command"] == c.cursor_native.hooks_json_command
    assert binding["implementation"] == c.cursor_native.implementation
    assert binding["blocking"] is c.cursor_native.blocking


def test_pattern_handler_read_api(tmp_path: Path) -> None:
    from omnicursor.nodes.node_cursor_pattern_injection_compute import handler as h

    p = tmp_path / "learned_patterns.json"
    p.write_text(
        '{"patterns": [{"domain": "git", "description": "always pull before push", "pattern_id": "1"}]}',
        encoding="utf-8",
    )
    out = h.read_patterns_for_prompt(p, "git workflow pull and push", domain="git")
    assert isinstance(out, list)

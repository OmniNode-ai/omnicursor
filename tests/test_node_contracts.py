"""OmniCursor node contracts — parity with OmniClaude contract layout, Cursor execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from omnicursor.node_contracts import (
    contracts_root,
    hooks_registration_ok,
    iter_contract_paths,
    load_all_contracts,
)


def test_contracts_root_contains_yaml() -> None:
    root = contracts_root()
    assert root.is_dir()
    paths = list(iter_contract_paths(root))
    assert len(paths) >= 5
    assert all(p.name == "contract.yaml" for p in paths)


def test_load_all_contracts_validates() -> None:
    contracts = load_all_contracts()
    names = {c.name for c in contracts}
    assert "node_cursor_prompt_orchestrator" in names
    assert "node_cursor_shell_guard_effect" in names
    assert "node_cursor_file_edit_effect" in names
    assert "node_cursor_session_outcome_orchestrator" in names
    assert "node_cursor_pattern_injection_compute" in names
    for c in contracts:
        assert c.cursor_native.hook_event
        assert c.cursor_native.implementation.startswith(".cursor/hooks/")


def test_hooks_json_matches_contracts() -> None:
    """When run from the OmniCursor repo, hooks.json commands match contracts."""
    repo_root = Path(__file__).resolve().parents[1]
    hooks = repo_root / ".cursor" / "hooks.json"
    if not hooks.is_file():
        pytest.skip("hooks.json not present (not OmniCursor repo checkout)")
    assert hooks_registration_ok(load_all_contracts())


def test_shell_guard_is_blocking() -> None:
    contracts = {c.name: c for c in load_all_contracts()}
    guard = contracts["node_cursor_shell_guard_effect"]
    assert guard.cursor_native.blocking is True
    assert contracts["node_cursor_prompt_orchestrator"].cursor_native.blocking is False

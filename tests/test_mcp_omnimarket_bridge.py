"""Tests for the omnicursor MCP omnimarket bridge server."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

import pytest

mcp_mod = pytest.importorskip("mcp", reason="mcp package not installed")

from omnicursor.mcp import omnimarket_bridge_server  # noqa: E402

_OK_RESULT: Dict[str, Any] = {
    "ok": True,
    "returncode": 0,
    "state": {"current_phase": "init", "dry_run": True},
    "stderr": "",
    "error": None,
    "command": ["python", "-m", "omnimarket.nodes.node_local_review", "--dry-run"],
    "cwd": "/fake/omnimarket",
    "python": "python",
}

_FAIL_RESULT: Dict[str, Any] = {
    "ok": False,
    "returncode": -1,
    "state": None,
    "stderr": "",
    "error": "Omnimarket checkout not found.",
    "command": [],
    "cwd": None,
    "python": "python",
}


class _BridgeSpy:
    def __init__(self, result: Dict[str, Any]) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._result = result

    def __call__(self, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append(kwargs)
        return self._result


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_tool_registered() -> None:
    tools = _run(omnimarket_bridge_server.mcp.list_tools())
    names = [t.name for t in tools]
    assert "run_local_review" in names
    assert "run_ticket_pipeline" in names
    assert "run_ci_watch" in names


def test_tool_calls_bridge_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _BridgeSpy(_OK_RESULT)
    monkeypatch.setattr(omnimarket_bridge_server.omnimarket_bridge, "run_local_review", spy)

    _run(omnimarket_bridge_server.mcp.call_tool("run_local_review", {}))

    assert len(spy.calls) == 1
    assert spy.calls[0] == {"dry_run": True, "max_iterations": 10, "required_clean_runs": 2}


def test_tool_forwards_custom_params(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _BridgeSpy(_OK_RESULT)
    monkeypatch.setattr(omnimarket_bridge_server.omnimarket_bridge, "run_local_review", spy)

    _run(omnimarket_bridge_server.mcp.call_tool(
        "run_local_review",
        {"dry_run": False, "max_iterations": 5, "required_clean_runs": 3},
    ))

    assert spy.calls[0] == {"dry_run": False, "max_iterations": 5, "required_clean_runs": 3}


def test_tool_returns_parseable_json(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _BridgeSpy(_OK_RESULT)
    monkeypatch.setattr(omnimarket_bridge_server.omnimarket_bridge, "run_local_review", spy)

    content_blocks, _structured = _run(
        omnimarket_bridge_server.mcp.call_tool("run_local_review", {})
    )

    text = content_blocks[0].text
    parsed = json.loads(text)
    assert parsed["ok"] is True
    assert parsed["state"]["current_phase"] == "init"


def test_tool_returns_error_as_json(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _BridgeSpy(_FAIL_RESULT)
    monkeypatch.setattr(omnimarket_bridge_server.omnimarket_bridge, "run_local_review", spy)

    content_blocks, _structured = _run(
        omnimarket_bridge_server.mcp.call_tool("run_local_review", {})
    )

    parsed = json.loads(content_blocks[0].text)
    assert parsed["ok"] is False
    assert "not found" in parsed["error"]


def test_default_dry_run_is_true(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _BridgeSpy(_OK_RESULT)
    monkeypatch.setattr(omnimarket_bridge_server.omnimarket_bridge, "run_local_review", spy)

    _run(omnimarket_bridge_server.mcp.call_tool("run_local_review", {}))

    assert spy.calls[0]["dry_run"] is True

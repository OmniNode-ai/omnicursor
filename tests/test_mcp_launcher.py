"""Smoke tests for the plugin-root-resolving MCP launcher (PR #10, point 4).

The launcher must start the server from an arbitrary working directory — a
sandbox workspace that is *not* this checkout — because it resolves the
plugin root from its own real path instead of ``${workspaceFolder}``.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = REPO_ROOT / ".cursor" / "mcp-launcher.py"

_HAS_MCP = True
try:  # the .[mcp] extra is optional
    import mcp  # noqa: F401
except ImportError:
    _HAS_MCP = False


def test_launcher_exists_and_is_wired_into_mcp_json() -> None:
    assert LAUNCHER.is_file()
    cfg = json.loads((REPO_ROOT / ".cursor" / "mcp.json").read_text())
    server = cfg["mcpServers"]["omnicursor-omnimarket"]
    assert server["args"] == ["${workspaceFolder}/.cursor/mcp-launcher.py"]
    # The launcher owns sys.path setup; a PYTHONPATH pin would reintroduce
    # the workspace-layout assumption the launcher exists to remove.
    assert "PYTHONPATH" not in server.get("env", {})


def test_launcher_fails_closed_without_plugin_src(tmp_path: Path) -> None:
    """Copied out of the plugin tree (no src/omnicursor sibling), the launcher
    must exit 1 with a diagnostic instead of importing whatever is ambient."""
    fake_cursor = tmp_path / ".cursor"
    fake_cursor.mkdir()
    orphan = fake_cursor / "mcp-launcher.py"
    shutil.copy(LAUNCHER, orphan)
    proc = subprocess.run(
        [sys.executable, str(orphan)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
    )
    assert proc.returncode == 1
    assert "no src/omnicursor under plugin root" in proc.stderr


@pytest.mark.skipif(not _HAS_MCP, reason="requires the .[mcp] extra")
def test_launcher_serves_initialize_and_tool_call_from_sandbox(
    tmp_path: Path,
) -> None:
    """Launch the server via the launcher from a sandbox cwd with no
    repo-pointing PYTHONPATH, then complete initialize -> tools/list ->
    tools/call over stdio."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    proc = subprocess.Popen(
        [sys.executable, str(LAUNCHER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    lines: queue.Queue[str] = queue.Queue()
    assert proc.stdout is not None and proc.stdin is not None
    threading.Thread(
        target=lambda: [lines.put(line) for line in proc.stdout],  # type: ignore[union-attr]
        daemon=True,
    ).start()

    def send(msg: dict) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def recv(expect_id: int, timeout_s: float = 30.0) -> dict:
        while True:
            raw = lines.get(timeout=timeout_s)
            msg = json.loads(raw)
            if msg.get("id") == expect_id:
                return msg

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0"},
                },
            }
        )
        init = recv(1)
        assert init["result"]["serverInfo"]["name"] == "omnicursor-omnimarket"

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = {t["name"] for t in recv(2)["result"]["tools"]}
        assert {"run_local_review", "run_ticket_pipeline"} <= tools

        # One real tool call. In the sandbox there is no omnimarket checkout,
        # so a structured isError response is a valid proof: the request
        # completed the full dispatch path and came back well-formed.
        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "run_local_review", "arguments": {"dry_run": True}},
            }
        )
        call = recv(3, timeout_s=60.0)
        assert "result" in call or "error" in call
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

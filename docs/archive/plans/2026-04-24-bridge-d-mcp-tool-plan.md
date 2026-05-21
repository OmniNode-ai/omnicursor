# BRIDGE-D: MCP Tool Wrapping the Omnimarket Bridge

**Date:** 2026-04-24
**Source:** BRIDGE-C (subprocess bridge delivered), sponsor alignment (2026-04-16)
**Status:** Preflight approved, not yet executed

---

## 1. MCP design

### Server

One `FastMCP` server in `src/omnicursor/mcp/omnimarket_bridge_server.py`. Uses `mcp.server.fastmcp.FastMCP` (v1.26.0 installed in venv).

```python
mcp = FastMCP("omnicursor-omnimarket")

@mcp.tool(description="Run Omnimarket node_local_review via subprocess against a local checkout.")
def run_local_review(
    dry_run: bool = True,
    max_iterations: int = 10,
    required_clean_runs: int = 2,
) -> str:
    result = omnimarket_bridge.run_local_review(
        dry_run=dry_run,
        max_iterations=max_iterations,
        required_clean_runs=required_clean_runs,
    )
    return json.dumps(result, indent=2, default=str)
```

Return type is `str` (JSON-serialized `BridgeResult`). `FastMCP` wraps it as a `TextContent` block. No `structured_output=True` — that requires a Pydantic return model, and `BridgeResult` is a `TypedDict`.

### Entrypoint

`__main__.py` in `src/omnicursor/mcp/` so `python -m omnicursor.mcp.omnimarket_bridge_server` works. Calls `mcp.run(transport="stdio")`.

### Transport

stdio — Cursor spawns the process and communicates over stdin/stdout.

---

## 2. Dependency decision

Add `mcp` as an **optional dependency** group `[project.optional-dependencies] mcp = ["mcp>=1.26.0,<2.0.0"]`. Rationale: the core library (hooks, agents, skills, compliance) must not require the heavy `mcp` dep tree (uvicorn, starlette, httpx, etc.). MCP users install with `pip install -e ".[mcp]"`.

Already installed in the venv so no `pip install` needed for current dev work.

---

## 3. Config location

`.cursor/mcp.json` — this is Cursor's standard MCP server config file, separate from `.cursor/settings.json` (which holds plugin config like Linear). Format:

```json
{
  "mcpServers": {
    "omnicursor-omnimarket": {
      "command": "python",
      "args": ["-m", "omnicursor.mcp.omnimarket_bridge_server"],
      "cwd": "<repo-root>",
      "env": {
        "OMNIMARKET_ROOT": "<path-to-local-omnimarket>"
      }
    }
  }
}
```

This file will be committed with placeholder comments. Users set `OMNIMARKET_ROOT` to their local checkout path.

---

## 4. Files to add/edit

| Action | Path | Notes |
|--------|------|-------|
| **Add** | `src/omnicursor/mcp/__init__.py` | Empty |
| **Add** | `src/omnicursor/mcp/omnimarket_bridge_server.py` | FastMCP server + one tool (~30 lines) |
| **Add** | `src/omnicursor/mcp/__main__.py` | `python -m omnicursor.mcp` entrypoint (imports and runs the server) |
| **Add** | `tests/test_mcp_omnimarket_bridge.py` | Tests via `mcp.call_tool()` + monkeypatched bridge (~60 lines) |
| **Add** | `.cursor/mcp.json` | Cursor MCP server config |
| **Edit** | `pyproject.toml` | Add `mcp` optional dependency group |

No changes to `omnimarket_bridge.py`, `schemas.py`, `compose.yaml`, or Docker.

---

## 5. Test plan

Tests use `FastMCP.call_tool()` directly — no transport/subprocess needed. Bridge is monkeypatched.

| Test | What it verifies |
|------|-----------------|
| `test_tool_registered` | `list_tools()` returns a tool named `run_local_review` |
| `test_tool_calls_bridge` | `call_tool("run_local_review", {"dry_run": true})` invokes `omnimarket_bridge.run_local_review(dry_run=True, ...)` |
| `test_tool_returns_json_text` | Result contains a `TextContent` block with valid JSON |
| `test_tool_forwards_params` | `max_iterations=5, required_clean_runs=3` forwarded to bridge |
| `test_tool_returns_error_on_bridge_failure` | Bridge returns `ok=False` → tool still returns JSON (not an exception) |
| `test_default_params` | No args → `dry_run=True, max_iterations=10, required_clean_runs=2` |

All tests are `async` (FastMCP methods are async). Use `pytest-anyio` or `asyncio` marker (anyio already installed per pytest plugins output).

---

## 6. Verification commands

```bash
ruff check src/omnicursor/mcp/ tests/test_mcp_omnimarket_bridge.py
pytest tests/test_mcp_omnimarket_bridge.py -v
pytest tests/ -v  # full suite, no regressions

# Manual: confirm server starts and lists tools
python -m omnicursor.mcp.omnimarket_bridge_server &
# (will block on stdio — kill after confirming no import errors)
```

---

## Out of scope

- Additional MCP tools beyond `run_local_review`
- Docker Compose changes
- `onex run` integration
- Direct omniintelligence HTTP calls
- Runtime GitHub cloning of omnimarket
- In-process handler import fallback

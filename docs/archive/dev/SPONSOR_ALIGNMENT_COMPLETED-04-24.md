# OmniCursor → Omnimarket Bridge — Session Summary

Julian Irusta Roure — April 24, 2026

---

## What is Omnimarket and why does it matter?

OmniNode is the platform layer that powers things like code review, quality scoring, and workflow automation across the team's repos. The problem was: how does OmniCursor (our Cursor IDE layer) talk to that platform?

The original approach was to call into the platform's internal services directly — the intelligence reducer, the orchestrator, the quality scoring engine. But our sponsor (Jonah) redirected that on April 16: those services are the wrong integration layer. They're internal plumbing.

**Omnimarket** is the right layer. It's a portable node registry — a collection of self-contained workflow packages that wrap platform behavior into callable units. Nodes like `node_local_review`, `node_hostile_reviewer`, `node_pr_polish`, and about 25 others. Each one can run locally with zero infrastructure. No Docker needed, no Kafka, no database. Just Python.

The sponsor's direction was clear: build a bridge from OmniCursor to Omnimarket, not to the services behind it. Start with one node, prove it works end-to-end, and ship it.

---

## What we did in this session

We built the full bridge in one session, working in three incremental batches. Each batch was planned before execution, scoped tightly, and verified before moving on.

### Step 1 — Made the repo safe and documented the conventions

Before writing any bridge code, we needed two things: make sure credentials wouldn't accidentally get committed, and establish how OmniCursor finds a local Omnimarket checkout.

We added `.env` and the local Omnimarket checkout directory (`omnimarket-main/`) to `.gitignore`. Then we documented the `OMNIMARKET_ROOT` convention in `CLAUDE.md` — this is the environment variable that tells OmniCursor where Omnimarket lives on disk. If it's not set, the bridge falls back to looking for `omnimarket-main/` in the repo root as a dev convenience.

We also documented the boundaries: Docker Compose is approved but isn't the primary bridge path. `onex run` and direct calls to intelligence services are out of scope. Omnimarket is never cloned from GitHub at runtime — it must already exist locally.

### Step 2 — Built the subprocess bridge

This is the core: a Python module (`omnimarket_bridge.py`) with one function, `run_local_review()`. It resolves the Omnimarket checkout location, builds the right command-line arguments, and runs:

```
python -m omnimarket.nodes.node_local_review --dry-run
```

The function captures everything — stdout, stderr, return code — parses the JSON output, and returns a structured result. If anything goes wrong (checkout not found, subprocess timeout, invalid output), the error is returned cleanly instead of crashing.

One finding during implementation: Omnimarket uses a `src/` layout, so just setting the working directory wasn't enough for Python to find the module. The bridge automatically injects the right `PYTHONPATH` into the subprocess environment.

We wrote 17 tests covering success, failure, CLI flag forwarding, root resolution, timeout handling, and the PYTHONPATH injection. All mocked — no real Omnimarket needed to run them.

Then we ran a real smoke test against the actual local Omnimarket checkout. It worked: `ok: true`, `current_phase: "init"`, `dry_run: true`.

### Step 3 — Wrapped it in an MCP tool for Cursor

The bridge works, but Cursor can't call a Python function directly. It needs an MCP server — a small process that Cursor spawns and communicates with over stdio.

We created a FastMCP server with one tool: `run_local_review`. When Cursor calls this tool, it runs the bridge function and returns the JSON result. The tool defaults to `dry_run=True` so it's safe to invoke during exploration.

We added `.cursor/mcp.json` so Cursor knows how to start the server, and added `mcp` as an optional dependency in `pyproject.toml` (the core library doesn't need it — only the MCP server does).

We wrote 6 tests for the MCP layer, then ran the full end-to-end: MCP tool call → bridge → subprocess → real `node_local_review` → JSON result back. It worked.

---

## The end-to-end path

```
Cursor IDE
  → MCP protocol (stdio)
    → FastMCP server (omnicursor-omnimarket)
      → run_local_review tool
        → omnimarket_bridge.run_local_review()
          → subprocess: python -m omnimarket.nodes.node_local_review --dry-run
            → Omnimarket node executes, outputs JSON
          → JSON parsed into structured result
        → returned as text to Cursor
```

One MCP tool, one bridge function, one subprocess call. That's the whole integration.

---

## What the sponsor asked for vs. what we delivered

The April 16 sponsor feedback said:

> "Before Monday, put a bridge.py in place that calls node_local_review via subprocess invocation, wire it through one MCP tool, and demonstrate one end-to-end call."

**Delivered:**
- `src/omnicursor/omnimarket_bridge.py` — the bridge
- `src/omnicursor/mcp/omnimarket_bridge_server.py` — the MCP server with one tool
- `.cursor/mcp.json` — Cursor config to connect to the server
- 23 new tests (17 bridge + 6 MCP), all passing
- Two real smoke tests: bridge-level and MCP-level, both successful
- Full test suite: 468 passed, 0 failures

---

## What we deliberately did not do

Following the sponsor's direction exactly:

- Did not expand Docker Compose — it's approved as-is but isn't the bridge path
- Did not use `onex run <contract.yaml>` — broken upstream routing validation
- Did not call intelligence services directly — wrong layer; Omnimarket wraps them
- Did not clone Omnimarket from GitHub at runtime — uses local checkout only
- Did not add upstream pattern writes — that's year-2, not capstone
- Did not add extra MCP tools — one tool, one node, prove it works first
- Did not build the in-process handler fallback — subprocess path works, no need yet

---

## Session metrics

| | Before | After |
|---|--------|-------|
| Tests | 445 | 468 |
| New files | — | 8 |
| Edited files | — | 4 |
| Plans created | — | 3 |
| Real smoke tests | — | 2 (both passed) |

---

## Next steps

1. Restart Cursor to pick up `.cursor/mcp.json` and test the tool from the MCP panel
2. Decide whether to harden this path for team handoff, add more Omnimarket nodes, or explore the in-process handler path for nodes without `__main__.py`

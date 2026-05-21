# Sponsor Follow-Up - Julian's OmniCursor to Omnimarket Bridge

Julian - OmniCursor Intelligence/Docker Track  
April 24, 2026

## TL;DR

The narrow bridge target from the April 16 sponsor feedback has been delivered:

- One MCP tool named `run_local_review`.
- The MCP tool calls an OmniCursor bridge module.
- The bridge invokes Omnimarket `node_local_review` through the local-first subprocess path:
  `python -m omnimarket.nodes.node_local_review`.
- Omnimarket is resolved as a local checkout/package via `OMNIMARKET_ROOT`.
- The result is captured, parsed as JSON, and returned back through MCP.

The implementation intentionally did not expand Docker, did not use `onex run`, did not call `omniintelligence` services directly, did not clone Omnimarket from GitHub at runtime, and did not add upstream pattern writes.

In short: OmniCursor can now trigger a real Omnimarket node from Cursor through one MCP tool, using the local-first path the sponsor asked for.

## Sponsor Direction Followed

The April 16 feedback redirected the work away from full Docker/runtime parity and toward a smaller local-first bridge. The implemented path follows that direction:

- Primary bridge layer is Omnimarket, not direct `omniintelligence` service APIs.
- First integration target is `node_local_review`.
- Invocation path is subprocess-based `python -m omnimarket.nodes.node_local_review`.
- `OMNIMARKET_ROOT` locates the local Omnimarket checkout.
- Repo-local `omnimarket-main/` is only a local development fallback.
- Docker Compose remains approved as-is, but it was not expanded and is not the primary bridge path.
- `onex run <contract.yaml>` remains out of scope because of the routing validation gaps called out in the sponsor feedback.
- Pattern writes remain local/team-owned; upstream intelligence writes remain out of capstone scope.

## What Changed

### BRIDGE-B - Repo Hygiene and Bridge Conventions

Purpose: make the repo safer and document the bridge conventions before adding code.

Completed:

- Added local env safety to `.gitignore`:
  - `.env`
  - `.env.local`
  - `.env.*.local`
- Kept local Omnimarket checkout artifacts out of git:
  - `omnimarket-main/`
  - `omnimarket-main.zip`
- Added an "Omnimarket bridge" section to `CLAUDE.md`.
- Documented `OMNIMARKET_ROOT`.
- Documented that Omnimarket is invoked as a local checkout/package.
- Documented that Omnimarket is never cloned from GitHub at runtime.
- Documented that Docker Compose is approved but not the bridge's primary path.
- Documented that `onex run` and direct `omniintelligence` HTTP calls are out of scope.

### BRIDGE-C - Subprocess Bridge to `node_local_review`

Purpose: give OmniCursor a small, typed bridge that can invoke Omnimarket without Docker.

Completed:

- Added `src/omnicursor/omnimarket_bridge.py`.
- Added `run_local_review(...)`.
- Supported:
  - `dry_run`
  - `max_iterations`
  - `required_clean_runs`
- Resolved Omnimarket through:
  - `OMNIMARKET_ROOT`
  - repo-local `omnimarket-main/` fallback for development only
- Resolved Python through:
  - `OMNIMARKET_PYTHON`
  - otherwise `sys.executable`
- Ran the subprocess with `cwd=OMNIMARKET_ROOT`.
- Captured stdout, stderr, return code, command, cwd, and Python executable.
- Parsed stdout JSON into a structured `BridgeResult`.
- Returned structured failures instead of raising exceptions.
- Injected `{OMNIMARKET_ROOT}/src` into subprocess `PYTHONPATH`, because Omnimarket uses a `src/` layout.
- Used `os.pathsep` for portable `PYTHONPATH` handling.

Implementation-time finding:

`cwd=OMNIMARKET_ROOT` was not enough by itself for `python -m omnimarket.nodes.node_local_review` when Omnimarket is a local source checkout. The subprocess also needs `{OMNIMARKET_ROOT}/src` in `PYTHONPATH` unless Omnimarket is installed as a package. The bridge handles this automatically.

### BRIDGE-D - MCP Tool

Purpose: expose the bridge to Cursor through one MCP tool.

Completed:

- Added `src/omnicursor/mcp/`.
- Added `src/omnicursor/mcp/omnimarket_bridge_server.py`.
- Created one `FastMCP("omnicursor-omnimarket")` server.
- Registered one MCP tool: `run_local_review`.
- Tool defaults are safe for discovery:
  - `dry_run=True`
  - `max_iterations=10`
  - `required_clean_runs=2`
- The MCP tool calls `omnicursor.omnimarket_bridge.run_local_review`.
- The MCP tool returns JSON text to Cursor.
- Added `src/omnicursor/mcp/__main__.py` so `python -m omnicursor.mcp` can start the server.
- Added `.cursor/mcp.json` for Cursor MCP registration.
- Added `mcp>=1.26.0,<2.0.0` as an optional dependency group in `pyproject.toml`.

## End-to-End Path

```text
Cursor
  -> MCP over stdio
  -> FastMCP server: omnicursor-omnimarket
  -> tool: run_local_review
  -> omnicursor.omnimarket_bridge.run_local_review(...)
  -> subprocess:
       python -m omnimarket.nodes.node_local_review --dry-run
  -> Omnimarket node stdout JSON
  -> BridgeResult
  -> JSON text returned to Cursor
```

## Verification Evidence

Baseline before BRIDGE-D:

- `462 passed`

After BRIDGE-D:

- `468 passed`

Bridge tests:

- `tests/test_omnimarket_bridge.py`
- `17 passed`

MCP tests:

- `tests/test_mcp_omnimarket_bridge.py`
- `6 passed`

Full suite:

- `468 passed`

Real bridge smoke:

- `OMNIMARKET_ROOT=/Users/jirustaroure/Desktop/OmniCursor/omnimarket-main`
- `run_local_review(dry_run=True)`
- Result: `ok: true`
- Parsed state included:
  - `current_phase: "init"`
  - `dry_run: true`

Real MCP-level smoke:

- `mcp.call_tool("run_local_review", {"dry_run": true})`
- Flow reached:
  - MCP server
  - OmniCursor bridge
  - subprocess invocation
  - Omnimarket `node_local_review`
- Result: `ok: true`
- Parsed state included:
  - `current_phase: "init"`
  - `dry_run: true`

Safety checks:

- No Docker expansion.
- No `onex run` usage.
- No direct `omniintelligence` service calls.
- No runtime GitHub clone.
- No upstream pattern write path.

## Files Added or Changed

Added:

- `src/omnicursor/omnimarket_bridge.py`
- `tests/test_omnimarket_bridge.py`
- `src/omnicursor/mcp/__init__.py`
- `src/omnicursor/mcp/__main__.py`
- `src/omnicursor/mcp/omnimarket_bridge_server.py`
- `tests/test_mcp_omnimarket_bridge.py`
- `.cursor/mcp.json`
- `docs/plans/2026-04-24-bridge-b-repo-hygiene-plan.md`
- `docs/plans/2026-04-24-bridge-c-subprocess-bridge-plan.md`
- `docs/plans/2026-04-24-bridge-d-mcp-tool-plan.md`

Changed:

- `.gitignore`
- `CLAUDE.md`
- `pyproject.toml`

## How to Corroborate Locally

From the OmniCursor repo:

```bash
cd /Users/jirustaroure/Desktop/OmniCursor
source .venv/bin/activate

ruff check src/omnicursor/omnimarket_bridge.py \
  src/omnicursor/mcp/ \
  tests/test_omnimarket_bridge.py \
  tests/test_mcp_omnimarket_bridge.py

pytest tests/test_omnimarket_bridge.py tests/test_mcp_omnimarket_bridge.py -v
pytest tests/ -v
```

Direct bridge smoke:

```bash
OMNIMARKET_ROOT=/Users/jirustaroure/Desktop/OmniCursor/omnimarket-main \
python - <<'PY'
from omnicursor.omnimarket_bridge import run_local_review
import json

print(json.dumps(run_local_review(dry_run=True), indent=2))
PY
```

MCP-level smoke:

```bash
OMNIMARKET_ROOT=/Users/jirustaroure/Desktop/OmniCursor/omnimarket-main \
python - <<'PY'
import asyncio
import json
from omnicursor.mcp.omnimarket_bridge_server import mcp

async def main():
    content_blocks, _ = await mcp.call_tool("run_local_review", {"dry_run": True})
    print(json.dumps(json.loads(content_blocks[0].text), indent=2))

asyncio.run(main())
PY
```

Cursor setup note:

Cursor may need to be restarted after `.cursor/mcp.json` is added. The MCP command must run in an environment where `omnicursor` and the optional `mcp` dependency are importable. The project venv works for this.

## What Was Not Chased

The implementation deliberately avoided the paths the sponsor said not to chase:

- No custom Docker image.
- No tighter `omnibase_infra` to `omniintelligence` runtime coupling.
- No direct calls to `intelligence-reducer`, `intelligence-orchestrator`, or `quality-scoring-compute`.
- No `onex run <contract.yaml>`.
- No full `omniintelligence` service parity.
- No upstream pattern write lifecycle.
- No extra MCP tools beyond `run_local_review`.
- No in-process Omnimarket handler fallback yet.

## Caveats and Next Review Questions

This delivers the first bridge target, but there are a few explicit boundaries:

- The current smoke uses `dry_run=True`, so it validates invocation, MCP transport, subprocess execution, and JSON parsing. It does not claim deeper review-loop semantics beyond what `node_local_review` currently executes in that mode.
- If the next goal is richer review behavior, the next batch should decide whether to deepen `node_local_review` inputs or move to the in-process handler path.
- Docker findings remain separate follow-ups. The bridge path does not depend on Docker.
- Cursor should be tested manually after restart to confirm the MCP tool appears and can be invoked from the Cursor MCP UI.

## Appendix A - April 16 Sponsor Feedback Converted to Markdown

Source PDF: `/Users/jirustaroure/Downloads/Julian_Sponsor_Response_2026-04-16.pdf`  
Converted Markdown: `docs/dev/Julian_Sponsor_Response_2026-04-16.md`

The text below is included for traceability so the delivered work can be checked directly against the sponsor's April 16 direction.

---

### Sponsor Response — Julian’s Intelligence/Docker Update

Jonah Gray — OmniNode.ai  
April 16, 2026

### TL;DR

Your investigation and the Docker Compose wrapper are good work. Approving both as-is.
One redirect before the weekend: scope all integration work to the local-first standalone runtime
before worrying about Docker infra. There’s a simpler bridge path than the one your mapping
pointed you toward — it removes work from your weekend plan rather than adds to it.
One honest caveat: the omnimarket repo has two different ways to invoke a node, and the headline onex run <contract.yaml> CLI path has real wiring gaps today (routing validation errors on many node contracts). The path that actually works is uv run python -m omnimarket.nodes.<node> for nodes that ship a __main__.py, or an in-process Python handler call.
Details below — you’ll want to know this before you pick a target.

### What’s Right

- Real codebase investigation across 4 repos (omniclaude, omnibase_infra, omniintelligence,
omnimemory) — that’s actual research, not hand-waving. The mapping is the foundation for
every decision downstream.
- Correctly identified the write-path gap: OmniCursor can consume learned patterns locally but
has no path for writing them back. Correct observation.
- Docker Compose wrapper inside OmniCursor is useful. PostgreSQL + Redpanda + Valkey +
the selected omniintelligence services is a reasonable local bring-up stack for isolated testing.
- Instinct to narrow before expanding is correct. Your weekend-plan framing (“narrow the integration path instead of pulling in the whole platform at once”) is the right strategy.

### The Simpler Bridge You May Have Missed

Your 4-repo mapping was thorough, but omnimarket is a newer sibling repo that wasn’t in your
list. It matters because it changes the integration story:
Omnimarket is a portable node registry. Nodes in omnimarket/src/omnimarket/nodes/
implement most of what OmniCursor would want to call into — node_hostile_reviewer,
node_local_review, node_pr_polish, node_aislop_sweep, and ~25 others. They are
executable in-process with zero external infrastructure (they use RuntimeLocal + EventBusInmemory from omnibase_core).
That means the Cursor -> OmniNode bridge you’ve been scoping can be a subprocess or in-process call into an already-tested omnimarket node. Same contracts, same handlers, same tests
that run today.

### Important Caveat — The Two Invocation Paths

There are two ways to call into an omnimarket node, and only one works cleanly today:

**Path A — `uv run onex run <contract.yaml>` (partially broken today)**

The headline CLI path takes a workflow contract YAML file. Omnimarket’s CLAUDE.md shows
an example ( uv run onex run node_aislop_sweep -- --dry-run ) but explicitly flags
it as “once RuntimeLocal wiring is complete.” That wiring is incomplete — running onex run
against current node contracts surfaces routing validation errors (missing event_model fields,
handler/topic length mismatches). Do not build against this path yet.

**Path B — `uv run python -m omnimarket.nodes.<node>` (works today)**

Nodes that ship a __main__.py can be invoked directly as a Python module. Verified work-
ing for node_local_review (argparse-based CLI with --dry-run flag). Nodes confirmed to have
__main__.py: node_local_review, node_ticket_pipeline, node_build_loop_orchestrator,
node_linear_triage, node_runtime_sweep.

**Path C — In-Process Python Import (works for every node)**

The golden-chain tests invoke node handlers directly:

```python
from omnimarket.nodes.node_hostile_reviewer.handlers.handler_hostile_reviewer import (
HandlerHostileReviewer,
)
from omnimarket.nodes.node_hostile_reviewer.models.model_hostile_reviewer_start_command import (
ModelHostileReviewerStartCommand,
)
handler = HandlerHostileReviewer()
command = ModelHostileReviewerStartCommand(...) # typed Pydantic input
state, events, completed = handler.run_full_pipeline(command)
```

This is the most robust bridge today because it bypasses the CLI entirely and is the same call
pattern the golden chain tests exercise.

### A Realistic Bridge Sketch

```python
# src/omnicursor/bridge.py
import json, os, subprocess
from pathlib import Path
OMNIMARKET_ROOT = Path(os.environ["OMNI_HOME"]) / "omnimarket"
def invoke_node_subprocess(node_module: str, args: list[str]) -> subprocess.CompletedProcess:
"""Subprocess path. Use only for nodes with __main__.py (see list above).
Arguments are argparse flags, not JSON."""
return subprocess.run(
["uv", "run", "python", "-m", node_module, *args],
cwd=OMNIMARKET_ROOT,
capture_output=True,
text=True,
check=True,
)
# In-process path lives in omnicursor as direct imports of omnimarket handlers.
# See golden chain tests in omnimarket/tests/test_golden_chain_*.py for the pattern.
```

Not 20 lines — closer to 30-40 once you handle Pydantic command construction and result parsing.
Plan for that.

### Scope Rule: Local-First Runtime Before Docker Infra

This is the one piece of direction worth being explicit about:
All OmniCursor -> OmniNode integration work should target the local-first standalone runtime
(Paths B or C above) before anything that requires Docker infra.
Concretely:
- First choice: uv run python -m omnimarket.nodes.<node> subprocess (Path B) for
nodes with __main__.py.
- Second choice: in-process Python handler import (Path C) for everything else.
- Third choice: your existing Docker Compose wrapper, only for skills that genuinely need a
service running.
- Not in scope: custom images, tighter runtime integration between omnibase_infra and
omniintelligence, direct API calls to intelligence services, or building against the onex
run <contract.yaml> CLI path until its routing validation is fixed.
This isn’t a new requirement — it’s a rule for what to build against. The in-process and python -m
paths already work today; you just have to point at them.

### Weekend Plan — Narrowed

Your 5-task weekend plan would produce planning artifacts. Swap it for 1 concrete task that ships
something:
This weekend: wire one MCP tool to node_local_review via subprocess invocation.

### Why This Target

- node_local_review has a working __main__.py with argparse ( --max-iterations, --
required-clean-runs, --dry-run).
- Invocation verified: uv run python -m omnimarket.nodes.node_local_review --
dry-run works today.
- It’s a meaningful end-to-end demonstration: the team can say “Cursor triggered a real omni-
market node and got back a result from the platform layer.”

### Effort Estimate

One focused work session if you stay within Path B. If you go in-process (Path C)

or touch the CLI wiring, budget more.

### Skip These Tasks From Your Original Plan

- “Identify which omniintelligence components are right first integration targets” — the answer
is “none directly; route through omnimarket nodes.”
- “Trace the pattern lifecycle across OmniNode repos” — capstone scope doesn’t need a full
lifecycle doc. Writes stay local in the PostgreSQL table Kailash is setting up.
- “Test whether the Docker stack is enough or need custom runtime” — the standalone in-process / python -m paths are enough. Confirmed. No custom runtime needed.
- “Define a minimal integration plan” — integration plan is “subprocess to python -m omni-
market.nodes.<node>, or in-process handler import.” One sentence, no doc.

### Approvals

- Docker Compose wrapper: approved AS-IS. Useful for isolated testing and for any future skill
that genuinely requires a running service. Do not expand it. Don’t add more omniintelligence
services unless a specific skill fails without one.
- Pattern writes stay local (PostgreSQL, as already scoped with Kailash). Bridging pattern
writes to upstream intelligence services is a year-2 feature, not a capstone deliverable.
- “Current Docker stack doesn’t reproduce full ONEX runtime” — correct observation. It doesn’t
need to. The in-process / python -m path is the workaround for exactly this; ONEX runtime
behavior is inside the omnimarket handler you call, not inside your local docker-compose
network.

### Things to Actively Not Chase

- “Custom image / tighter runtime integration.” Not needed. Not in scope. Don’t go down this
path.
- Direct calls to intelligence-reducer / intelligence-orchestrator / quality-scoring-compute. Wrong layer. If intelligence behavior is needed, call the omnimarket
node that wraps it.
- The onex run <contract.yaml> CLI path — currently has routing validation errors on
many node contracts. Wait for that wiring to land before building against it. Use Path B or
Path C until then.
- Full omniintelligence service parity. Capstone does not need this. Anything the demo requires from those services should route through a single omnimarket node, not through direct
service-to-service calls.

### Net

Your mapping work is the right groundwork. The Docker wrapper is useful. The gap you identified
is real. All approved.
The one redirect: before Monday, put a bridge.py in place that calls node_local_review via
uv run python -m omnimarket.nodes.node_local_review , wire it through one MCP tool,
and demonstrate one end-to-end call. That’s the smallest shippable version of “OmniCursor talks
to OmniNode” using a path that works today. Everything else can wait.
If you hit unexpected wiring gaps, flag them and we can decide whether to fix or route around.
Don’t burn a weekend debugging omnimarket CLI internals.
Jonah

## Ask
Please confirm whether this satisfies the April 16 target:

"Wire one MCP tool to `node_local_review` via subprocess invocation and demonstrate one end-to-end call."

If approved, the next decision is whether to:

1. Harden this MCP demo path for handoff.
2. Add a richer Omnimarket node invocation.
3. Explore the in-process handler path for nodes without `__main__.py`.
4. Defer Docker reproducibility and migration follow-ups to a separate batch.

<!-- Converted from /Users/jirustaroure/Downloads/Julian_Sponsor_Response_2026-04-16.pdf -->

# Sponsor Response — Julian’s Intelligence/Docker Update

Jonah Gray — OmniNode.ai  
April 16, 2026

## TL;DR

Your investigation and the Docker Compose wrapper are good work. Approving both as-is.

One redirect before the weekend: scope all integration work to the local-first standalone runtime before worrying about Docker infra. There’s a simpler bridge path than the one your mapping pointed you toward — it removes work from your weekend plan rather than adds to it.

One honest caveat: the `omnimarket` repo has two different ways to invoke a node, and the headline `onex run <contract.yaml>` CLI path has real wiring gaps today (routing validation errors on many node contracts). The path that actually works is `uv run python -m omnimarket.nodes.<node>` for nodes that ship a `__main__.py`, or an in-process Python handler call.

Details below — you’ll want to know this before you pick a target.

## What’s Right

- Real codebase investigation across 4 repos (`omniclaude`, `omnibase_infra`, `omniintelligence`, `omnimemory`) — that’s actual research, not hand-waving. The mapping is the foundation for every decision downstream.
- Correctly identified the write-path gap: OmniCursor can consume learned patterns locally but has no path for writing them back. Correct observation.
- Docker Compose wrapper inside OmniCursor is useful. PostgreSQL + Redpanda + Valkey + the selected `omniintelligence` services is a reasonable local bring-up stack for isolated testing.
- Instinct to narrow before expanding is correct. Your weekend-plan framing (“narrow the integration path instead of pulling in the whole platform at once”) is the right strategy.

## The Simpler Bridge You May Have Missed

Your 4-repo mapping was thorough, but `omnimarket` is a newer sibling repo that wasn’t in your list. It matters because it changes the integration story:

Omnimarket is a portable node registry. Nodes in `omnimarket/src/omnimarket/nodes/` implement most of what OmniCursor would want to call into — `node_hostile_reviewer`, `node_local_review`, `node_pr_polish`, `node_aislop_sweep`, and ~25 others. They are executable in-process with zero external infrastructure (they use `RuntimeLocal` + `EventBusInmemory` from `omnibase_core`).

That means the Cursor -> OmniNode bridge you’ve been scoping can be a subprocess or in-process call into an already-tested `omnimarket` node. Same contracts, same handlers, same tests that run today.

## Important Caveat — The Two Invocation Paths

There are two ways to call into an `omnimarket` node, and only one works cleanly today:

### Path A — `uv run onex run <contract.yaml>` (partially broken today)

The headline CLI path takes a workflow contract YAML file. Omnimarket’s `CLAUDE.md` shows an example (`uv run onex run node_aislop_sweep -- --dry-run`) but explicitly flags it as “once RuntimeLocal wiring is complete.” That wiring is incomplete — running `onex run` against current node contracts surfaces routing validation errors (missing `event_model` fields, handler/topic length mismatches). Do not build against this path yet.

### Path B — `uv run python -m omnimarket.nodes.<node>` (works today)

Nodes that ship a `__main__.py` can be invoked directly as a Python module. Verified working for `node_local_review` (argparse-based CLI with `--dry-run` flag). Nodes confirmed to have `__main__.py`:

- `node_local_review`
- `node_ticket_pipeline`
- `node_build_loop_orchestrator`
- `node_linear_triage`
- `node_runtime_sweep`

### Path C — In-Process Python Import (works for every node)

The golden-chain tests invoke node handlers directly:

```python
from omnimarket.nodes.node_hostile_reviewer.handlers.handler_hostile_reviewer import (
    HandlerHostileReviewer,
)
from omnimarket.nodes.node_hostile_reviewer.models.model_hostile_reviewer_start_command import (
    ModelHostileReviewerStartCommand,
)

handler = HandlerHostileReviewer()
command = ModelHostileReviewerStartCommand(...)  # typed Pydantic input
state, events, completed = handler.run_full_pipeline(command)
```

This is the most robust bridge today because it bypasses the CLI entirely and is the same call pattern the golden-chain tests exercise.

## A Realistic Bridge Sketch

```python
# src/omnicursor/bridge.py
import json
import os
import subprocess
from pathlib import Path

OMNIMARKET_ROOT = Path(os.environ["OMNI_HOME"]) / "omnimarket"


def invoke_node_subprocess(
    node_module: str,
    args: list[str],
) -> subprocess.CompletedProcess:
    """Subprocess path. Use only for nodes with __main__.py (see list above).

    Arguments are argparse flags, not JSON.
    """
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

Not 20 lines — closer to 30-40 once you handle Pydantic command construction and result parsing. Plan for that.

## Scope Rule: Local-First Runtime Before Docker Infra

This is the one piece of direction worth being explicit about:

All OmniCursor -> OmniNode integration work should target the local-first standalone runtime (Paths B or C above) before anything that requires Docker infra.

Concretely:

- First choice: `uv run python -m omnimarket.nodes.<node>` subprocess (Path B) for nodes with `__main__.py`.
- Second choice: in-process Python handler import (Path C) for everything else.
- Third choice: your existing Docker Compose wrapper, only for skills that genuinely need a service running.
- Not in scope: custom images, tighter runtime integration between `omnibase_infra` and `omniintelligence`, direct API calls to intelligence services, or building against the `onex run <contract.yaml>` CLI path until its routing validation is fixed.

This isn’t a new requirement — it’s a rule for what to build against. The in-process and `python -m` paths already work today; you just have to point at them.

## Weekend Plan — Narrowed

Your 5-task weekend plan would produce planning artifacts. Swap it for 1 concrete task that ships something:

This weekend: wire one MCP tool to `node_local_review` via subprocess invocation.

Why this target:

- `node_local_review` has a working `__main__.py` with argparse (`--max-iterations`, `--required-clean-runs`, `--dry-run`).
- Invocation verified: `uv run python -m omnimarket.nodes.node_local_review --dry-run` works today.
- It’s a meaningful end-to-end demonstration: the team can say “Cursor triggered a real `omnimarket` node and got back a result from the platform layer.”

Effort estimate: one focused work session if you stay within Path B. If you go in-process (Path C) or touch the CLI wiring, budget more.

## Skip These Tasks From Your Original Plan

- “Identify which `omniintelligence` components are right first integration targets” — the answer is “none directly; route through `omnimarket` nodes.”
- “Trace the pattern lifecycle across OmniNode repos” — capstone scope doesn’t need a full lifecycle doc. Writes stay local in the PostgreSQL table Kailash is setting up.
- “Test whether the Docker stack is enough or need custom runtime” — the standalone in-process / `python -m` paths are enough. Confirmed. No custom runtime needed.
- “Define a minimal integration plan” — integration plan is “subprocess to `python -m omnimarket.nodes.<node>`, or in-process handler import.” One sentence, no doc.

## Approvals

- Docker Compose wrapper: approved AS-IS. Useful for isolated testing and for any future skill that genuinely requires a running service. Do not expand it. Don’t add more `omniintelligence` services unless a specific skill fails without one.
- Pattern writes stay local (PostgreSQL, as already scoped with Kailash). Bridging pattern writes to upstream intelligence services is a year-2 feature, not a capstone deliverable.
- “Current Docker stack doesn’t reproduce full ONEX runtime” — correct observation. It doesn’t need to. The in-process / `python -m` path is the workaround for exactly this; ONEX runtime behavior is inside the `omnimarket` handler you call, not inside your local `docker-compose` network.

## Things to Actively Not Chase

- “Custom image / tighter runtime integration.” Not needed. Not in scope. Don’t go down this path.
- Direct calls to `intelligence-reducer` / `intelligence-orchestrator` / `quality-scoring-compute`. Wrong layer. If intelligence behavior is needed, call the `omnimarket` node that wraps it.
- The `onex run <contract.yaml>` CLI path — currently has routing validation errors on many node contracts. Wait for that wiring to land before building against it. Use Path B or Path C until then.
- Full `omniintelligence` service parity. Capstone does not need this. Anything the demo requires from those services should route through a single `omnimarket` node, not through direct service-to-service calls.

## Net

Your mapping work is the right groundwork. The Docker wrapper is useful. The gap you identified is real. All approved.

The one redirect: before Monday, put a `bridge.py` in place that calls `node_local_review` via `uv run python -m omnimarket.nodes.node_local_review`, wire it through one MCP tool, and demonstrate one end-to-end call. That’s the smallest shippable version of “OmniCursor talks to OmniNode” using a path that works today. Everything else can wait.

If you hit unexpected wiring gaps, flag them and we can decide whether to fix or route around. Don’t burn a weekend debugging `omnimarket` CLI internals.

Jonah

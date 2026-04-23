# Sponsor alignment — 2026-04-16

Condensed from written sponsor feedback (hook port review + intelligence/Docker / omnimarket integration review). Aligns **long-term omniclaude-style depth** with **capstone scope** — capstone stays **foundation-first**, not full surface parity with omniclaude.

**Source PDFs (repo root / team folder):** sponsor response and agenda PDFs dated 2026-04-15–16.

## Work tracks (avoid duplicating ownership in docs)

| Track | Sponsor-relevant scope |
|--------|-------------------------|
| **Port (agents / skills / nodes)** | OmniClaude → OmniCursor port of `.cursor/agents`, `skills/*`, `src/omnicursor/nodes/*` — [MIGRATION_PHASES_HANDOFF.md](./MIGRATION_PHASES_HANDOFF.md) |
| **This repo (hooks + library)** | Hooks, remaining `src/omnicursor`, rules tied to hooks; optional `OMNICURSOR_PATTERN_SYNC_HTTP` behavior on stop |
| **External integration** | Omnimarket-facing MCP bridge, Docker/local stack, outward OmniNode wiring — **not** implied by edits to this checklist |
| **Pattern persistence** | Long-lived store / PostgreSQL / `store_pattern` — consume a defined read contract in hooks when it exists |
| **CI** | Pipeline and green baseline for this repository |

[MIGRATION_PHASES_HANDOFF.md](./MIGRATION_PHASES_HANDOFF.md) lists the **port track** for this repo (agents, skills, ONEX nodes & contracts). Hooks, Kafka, Linear-in-hooks, MCP bridge, and pattern-write work stay in [OMNICURSOR_MIGRATION_PLAN.md](../OMNICURSOR_MIGRATION_PLAN.md) / other tracks.

---

## Hooks / OmniCursor core (sponsor hook review)

- **Approved as-is:** Four Cursor hooks are the correct ceiling; correlation IDs and the four-way stop classifier match the intended omniclaude contract story.
- **Honest platform limit:** Only **`beforeShellExecution`** can *block* execution. OmniCursor is knowledge + observability around that single enforcement point — not a shortcoming of the implementation.
- **Workarounds approved:** Fake `SessionStart` (first prompt per `conversation_id` session dir), `.cursor/rules/` as *non-blocking* PreToolUse stand-in, MCP tools as *advisory* PostToolUse-style checks (hard gates stay on hooks).
- **Housekeeping (optional):** Note why **17** agent JSON files exist if a plan said 15; document whether shell patterns were copied from omniclaude `bash_guard.py` or hand-picked (future sync).

---

## OmniNode bridge (sponsor integration review)

- **Primary seam is `omnimarket`,** not direct calls to omniintelligence reducers/orchestrators/quality-scoring services. Those services are the wrong layer for capstone integration.
- **Invocation paths (2026-04-16):**
  - **Avoid:** `uv run onex run <contract.yaml>` until routing validation is fixed upstream.
  - **Prefer:** `uv run python -m omnimarket.nodes.<node>` for nodes with `__main__.py` (e.g. `node_local_review`).
  - **Robust:** In-process handler import + Pydantic command (same pattern as omnimarket golden-chain tests).
- **Order:** **Local-first** (Path B or C) before expanding Docker Compose. Compose stays **narrow** — useful for skills that truly need a service, not the default integration path.
- **Shippable demo target:** One **MCP tool** invoking **`node_local_review`** via subprocess (Path B), end-to-end.
- **Patterns (capstone):** **Writes** stay **local** (e.g. PostgreSQL — team-coordinated). **Bridging pattern writes to upstream intelligence** is explicitly **out of capstone** (year-2). Optional **HTTP pull** of patterns from a dev omniintelligence instance may be used for experimentation only — **not** the authoritative capstone path.

---

## Environment variables (implementation)

| Variable | Purpose |
|----------|---------|
| `OMNICURSOR_PATTERN_SYNC_HTTP` | Set to `1` / `true` / `yes` to run `GET /api/v1/patterns` on **stop** and refresh `learned_patterns.json`. **Default: off** (aligned with sponsor). |

---

## Related docs

- [OMNICURSOR_MIGRATION_PLAN.md](../OMNICURSOR_MIGRATION_PLAN.md) — full phase map.
- [MIGRATION_PHASES_HANDOFF.md](./MIGRATION_PHASES_HANDOFF.md) — port track (agents, skills, nodes & contracts); not the hooks/bus/MCP checklist.
- [CURSOR_FEATURE_SURFACE_MAP.md](./CURSOR_FEATURE_SURFACE_MAP.md) — Cursor surfaces; omnimarket MCP is sponsor integration priority, **separate** from this repo’s default build list.

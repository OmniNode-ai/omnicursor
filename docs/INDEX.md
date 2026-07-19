# Documentation Index

The map of OmniCursor's active documentation. Start here.

> **Source-of-truth order:** actual code → these docs. If a doc disagrees with
> the code, the code wins.

## Read this first

| Order | Document | What it gives you |
|-------|----------|-------------------|
| 1 | [`../README.md`](../README.md) | One-page product shape, install, hooks table |
| 2 | [`ARCHITECTURE.md`](./ARCHITECTURE.md) | How the surfaces + library fit together |
| 3 | [`CURRENT_STATE.md`](./CURRENT_STATE.md) | What works today, opt-in tiers, known drift |
| 4 | [`QUICKSTART.md`](./QUICKSTART.md) | Install as a Cursor plugin; hooks/skills behavior; Linear MCP |

## Active documents

| File | Scope |
|------|-------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Surfaces, hooks, routing, node contracts, learning loop, event emission, bridge, packaging |
| [`CURRENT_STATE.md`](./CURRENT_STATE.md) | Snapshot of what is built / opt-in / drifting; tests & CI; branches |
| [`QUICKSTART.md`](./QUICKSTART.md) | End-user setup and usage |
| [`W4_INJECTION_EVIDENCE.md`](./W4_INJECTION_EVIDENCE.md) | Injection proof (scoped verdict), sentinel receipt protocol, open residuals R1–R4 |

## By task

| I want to… | Read |
|------------|------|
| Understand the whole system | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| Know what actually works right now | [`CURRENT_STATE.md`](./CURRENT_STATE.md) |
| Install and use the plugin | [`QUICKSTART.md`](./QUICKSTART.md) |
| Change agent routing | [`ARCHITECTURE.md` §5](./ARCHITECTURE.md#5-agent-routing) → `src/omnicursor/scoring.py`, `.cursor/agents/`, `eval/` |
| Change hook behavior | [`ARCHITECTURE.md` §4](./ARCHITECTURE.md#4-hooks) → `.cursor/hooks/scripts/`, `tests/` |
| Add or change a skill | [`ARCHITECTURE.md` §3](./ARCHITECTURE.md#3-skills) → `skills/`, `.cursor/skills/`, `compliance.py`, tests |
| Work on event emission | [`ARCHITECTURE.md` §8](./ARCHITECTURE.md#8-event-emission) → `.cursor/hooks/lib/emit_client.py` (shared platform emit daemon) |
| Wire the OmniMarket bridge / MCP | [`ARCHITECTURE.md` §9](./ARCHITECTURE.md#9-omnimarket-bridge--mcp) → `OMNIMARKET_ROOT` |
| Verify context injection actually works | [`W4_INJECTION_EVIDENCE.md`](./W4_INJECTION_EVIDENCE.md) → `OMNICURSOR_INJECTION_SENTINEL=1` sentinel protocol |

## Planned documents

Deeper-dive docs that do not exist yet, listed (without links) so the map is honest.

**Referenced from the codebase but not yet written** — code/docstrings already
point at these paths:

- `dev/OMNICLAUDE_TO_CURSOR_PORT.md` — the library-vs-hook delegation & dual execution model *(cited in `user-prompt-submit.py`)*
- `dev/OMNICURSOR_NODE_CONTRACTS.md` — the ONEX-shaped contract concept, in depth *(cited in `nodes/__init__.py`)*
- `dev/ROUTING_DEDUPLICATION.md` — `scoring.py` as the single source of truth *(cited in `scoring.py`, `agent_scoring.py`)*

**Recommended (not yet referenced anywhere)** — proposed to close documentation gaps:

- `dev/EVENT_EMISSION.md` — `events.jsonl` vs `outbox.jsonl` vs `emit.sock`, shared platform emit daemon
- `dev/PATTERN_LEARNING_LOOP.md` — the end-to-end learning loop
- `dev/ENVIRONMENT_VARIABLES.md` — single env-var reference matrix
- `dev/STATE_FILES.md` — the `~/.omnicursor/` on-disk contract
- `CONTRIBUTING.md` — add-a-skill / add-an-agent multi-file invariants
- `dev/LOCAL_INFRA.md` — `compose.yaml` services, profiles, Options A/B

> Until those exist, [`ARCHITECTURE.md`](./ARCHITECTURE.md) covers the same
> ground at an overview level.

## Maintenance

When behavior changes (a hook, the skill/agent count, an Option's status, the
test count), update [`CURRENT_STATE.md`](./CURRENT_STATE.md) and the relevant
section of [`ARCHITECTURE.md`](./ARCHITECTURE.md) — and bump the "verified" date.

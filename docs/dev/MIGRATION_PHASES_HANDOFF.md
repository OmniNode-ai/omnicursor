# OmniCursor migration — port track (agents, skills, ONEX nodes & contracts)

**Scope:** Port OmniClaude’s **agents** (→ `.cursor/agents/*.json`), **skills** (→ `skills/*.md` + compliance + rules as needed), and **ONEX nodes** (→ `src/omnicursor/nodes/` with `contract.yaml`, handlers, tests). Use `omniclaude-main/` **read-only** as reference.

**Out of scope for this checklist** (see [OMNICURSOR_MIGRATION_PLAN.md](../OMNICURSOR_MIGRATION_PLAN.md) for the full repo map): Kafka / emit **daemon**, Linear-in-hooks / DoD hook work, omnimarket **MCP** bridge, Docker stack, authoritative pattern **writes** / PostgreSQL / `store_pattern`, CI pipeline ownership, optional `OMNICURSOR_PATTERN_SYNC_HTTP` behavior.

Sponsor context: [SPONSOR_ALIGNMENT_2026-04-16.md](./SPONSOR_ALIGNMENT_2026-04-16.md)

**References:** [OMNICURSOR_MIGRATION_PLAN.md](../OMNICURSOR_MIGRATION_PLAN.md), [OMNICURSOR_NODE_CONTRACTS.md](./OMNICURSOR_NODE_CONTRACTS.md), [CURSOR_FEATURE_SURFACE_MAP.md](./CURSOR_FEATURE_SURFACE_MAP.md)

---

## Verification (every PR)

- [ ] `ruff check src/ tests/ .cursor/hooks/`
- [ ] `pytest tests/ -v` (skill compliance runs in CI / pre-commit)

---

## Phase A — Agent coverage (17 → 53)

- [ ] Inventory OmniClaude agents not yet in `.cursor/agents/*.json`
- [ ] Port missing agents to JSON: `name`, `description`, `category`, `activation_patterns` (`explicit_triggers`, `context_triggers`, `activation_keywords`), `instructions`, `recommended_skill`
- [ ] Refresh routing tests / fixtures if activation phrases change materially
- [ ] Confirm agent JSON loads and routing tests pass (`src/omnicursor/agents.py` + hook routing stays consistent with library scoring)

**Done when:** Target agent count and CI green for routing.

---

## Phase B — Skill coverage (12 → 80+)

- [ ] Bucket 1: port skills with no external deps → `skills/<name>.md`
- [ ] Register each in `compliance.py`; update `tests/test_compliance.py` / `tests/test_skills.py` when the registry changes
- [ ] Add or adjust `.cursor/rules/*.mdc` for keyword activation where required
- [ ] Bucket 2: path-only adjustments vs OmniClaude sources
- [ ] Bucket 3: stub skills with explicit “manual / dry-run” labeling (no silent Kafka/Linear/API simulation)

**Done when:** Planned bucket counts met; `pytest` + compliance check pass.

---

## Phase C — ONEX nodes & contracts (`src/omnicursor/nodes/`)

- [ ] Evolve existing `node_cursor_*` stubs: `contract.yaml`, `handler.py`, tests per [OMNICURSOR_NODE_CONTRACTS.md](./OMNICURSOR_NODE_CONTRACTS.md)
- [ ] Add missing ported nodes from OmniClaude as needed (orchestrators, effects, compute) — keep handlers small, behavior declared in `contract.yaml`
- [ ] `node_cursor_pattern_injection_compute`: align **read** side with file-based patterns / loader contracts only; **no** authoritative upstream writes here — persistence shape is the **pattern persistence** track

**Done when:** Contracts validate, unit tests pass, and docs match the node set.

---

## Cross-cutting (port work)

- `omniclaude-main/` — **read-only** reference
- New skills: **never** skip `compliance.py` + tests
- ONEX invariants: behavior in `contract.yaml`, thin handlers, match `omnibase_core` expectations where applicable
- Bucket 3 skills: label external deps; do not fake integrations

---

## Handoff note

When stopping work, add or update a dated manifest under [handoffs/](./handoffs/) (see `skills/handoff.md`) with: branch, agents/skills/nodes touched, tests run, and the next three port tasks.

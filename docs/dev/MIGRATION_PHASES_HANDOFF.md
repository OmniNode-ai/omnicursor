# OmniCursor migration — port track (foundation-first)

**Scope:** Maintain a **strong Cursor-native foundation**: **agents** (`.cursor/agents/*.json` + `src/omnicursor/agents.py`), **skills** (`skills/*.md` + `compliance.py` + rules as needed), and **ONEX nodes** (`src/omnicursor/nodes/` with `contract.yaml`, handlers, tests). Use `omniclaude-main/` **read-only** as **patterns reference** — not a list to fully port.

**Out of scope** (see [OMNICURSOR_MIGRATION_PLAN.md](../OMNICURSOR_MIGRATION_PLAN.md)): Kafka emit **daemon**, Linear-in-hooks / DoD hook work, omnimarket **MCP** bridge, Docker stack, authoritative pattern **writes** / PostgreSQL / `store_pattern`, CI pipeline ownership, optional `OMNICURSOR_PATTERN_SYNC_HTTP` behavior.

Sponsor context: [SPONSOR_ALIGNMENT_2026-04-16.md](./SPONSOR_ALIGNMENT_2026-04-16.md)

**References:** [OMNICURSOR_MIGRATION_PLAN.md](../OMNICURSOR_MIGRATION_PLAN.md), [OMNICURSOR_NODE_CONTRACTS.md](./OMNICURSOR_NODE_CONTRACTS.md), [CURSOR_FEATURE_SURFACE_MAP.md](./CURSOR_FEATURE_SURFACE_MAP.md)

**Numbering:** [OMNICURSOR_MIGRATION_PLAN.md](../OMNICURSOR_MIGRATION_PLAN.md) uses **Phase 1–7** (hooks, agents, skills, nodes, …). **Phase 1** below is the **per-PR verification** gate. **Phase A / B / C** are the **foundation** workstreams (not “port everything from omniclaude”).

---

## Phase 1 — Verification (every PR)

**Baseline on `main` (2026-04-22):** commands below were run with the project `.venv` (`ruff` + `pytest`); results recorded here. **Still run them on every PR** — CI runs the same checks (`.github/workflows/ci.yml`).

- [x] `ruff check src/ tests/ .cursor/hooks/`
- [x] `pytest tests/ -v` (skill compliance runs in CI / pre-commit; **387** tests passed locally)

---

## Phase A — Agent layer (foundation)

**Principle:** The **current** `.cursor/agents/*.json` pool (on the order of **~17** files, including Cursor-specific agents such as `handoff`) **is the foundation**. Add or change JSON agents **when a workflow requires it**; use omniclaude only as **reference** for schema and phrasing.

- [x] Agent JSON present with required fields: `name`, `description`, `category`, `activation_patterns` (`explicit_triggers`, `context_triggers`, `activation_keywords`), `instructions`, `recommended_skill` (for each shipped file)
- [x] `src/omnicursor/agents.py` loads JSON and merges with hardcoded contexts; hook routing stays consistent with library scoring (`tests/test_agents.py` + hook suites)
- [ ] *(Optional)* Add or tune agents when capstone/product work needs new routing or background-agent configs

**Done when:** Foundation agent set + routing tests stay green in CI. **Not** done when: “matched omniclaude’s full agent catalog.”

---

## Phase B — Skill layer (foundation)

**Principle:** Ship **~12 methodology skills** today; treat **~17 curated skills** as a **soft ceiling** unless the team explicitly widens scope. **Do not** chase omniclaude’s 80+ skills.

- [x] Each `skills/*.md` (excluding `README.md`) has a `compliance.py` entry and test coverage in CI
- [x] Bucket-style discipline: new ports prefer **no external deps**; any skill that touches Kafka/Linear/APIs must be **explicitly manual / dry-run** (no silent fakes)
- [ ] Add or adjust `.cursor/rules/*.mdc` when a **new** skill needs keyword activation
- [ ] *(Optional)* Port additional omniclaude methodology **only** when a concrete workflow needs it

**Done when:** `pytest` + compliance check pass and skill count stays within the **curated** band the team agreed on.

---

## Phase C — ONEX nodes & contracts (`src/omnicursor/nodes/`)

**Principle:** **Five** Cursor-native contracts are the **foundation** (four lifecycle hooks + one read-side pattern compute). Execution stays in **stdlib hooks**; each node has `contract.yaml` + thin `handler.py` + tests for binding and (for patterns) **read-only** selection logic in `src/omnicursor/prompt_pattern_read.py`.

- [x] Contracts + `hooks.json` alignment per [OMNICURSOR_NODE_CONTRACTS.md](./OMNICURSOR_NODE_CONTRACTS.md); `handler.py` documents hook binding for all five nodes
- [x] `node_cursor_pattern_injection_compute`: **read** path for `learned_patterns.json` via library module only — **no** upstream writes (persistence / HTTP refresh remain separate tracks)
- [ ] *(Optional)* Add more nodes or deepen hook logic only when a consumer or demo requires it

**Done when:** Contracts validate, `tests/test_node_contracts.py` + `tests/test_node_handlers.py` + `tests/test_prompt_pattern_read.py` pass — **met for foundation (2026-04-22).**

---

## Cross-cutting (port work)

- `omniclaude-main/` — **read-only** reference
- New skills: **never** skip `compliance.py` + tests
- ONEX invariants: behavior in `contract.yaml`, thin handlers, match `omnibase_core` expectations where applicable
- External-dep skills: label honestly; do not fake integrations

---

## Handoff note

When stopping work, add or update a dated manifest under [handoffs/](./handoffs/) (see `.cursor/skills/handoff/SKILL.md`) with: branch, agents/skills/nodes touched, tests run, and the next **concrete** tasks (not “port more of omniclaude” unless scoped).

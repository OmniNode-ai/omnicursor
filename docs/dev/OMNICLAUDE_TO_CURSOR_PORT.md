# Porting OmniClaude behavior to Cursor execution

OmniClaude runs inside Claude Code with a Kafka-backed ONEX runtime, rich hook
types, and Python handlers that import the monorepo. **OmniCursor** runs inside
Cursor with **four hook events**, **stdlib-only hook processes**, and the same
**contract.yaml** shape under `src/omnicursor/nodes/` for CI and documentation.

This note explains **where logic lives**, **what must stay duplicated**, and
**how we avoid silent drift** when sharing algorithms between hooks and the
`omnicursor` Python package.

---

## 1. Two execution planes

| Plane | Location | May import | Role |
|-------|-----------|------------|------|
| **Hooks** | `.cursor/hooks/scripts/*.py` | Stdlib + repo-local `lib/` only | Deterministic gates, stdin/stdout JSON, no pip deps |
| **Library** | `src/omnicursor/` | Pydantic, YAML, tests | Routing metadata, contracts, compliance, `pytest` |

Hooks **must not** `import omnicursor`: that would drag non-stdlib code into the
hook process, break “Cursor runs `python3` on a script” assumptions, and couple
IDE lifecycle to package install layout.

---

## 2. Pattern relevance (learned patterns → prompt) — **single source**

**Problem:** The same OmniClaude-style relevance filter (domain base score +
keyword overlap, threshold 0.7, cap 5 patterns) was implemented twice: in
`user-prompt-submit.py` and in `omnicursor.prompt_pattern_read`, risking drift.

**Resolution:** One **stdlib-only** module is canonical:

- **`.cursor/hooks/lib/prompt_pattern_selection.py`**

The `beforeSubmitPrompt` hook imports it from `lib/` (already on `sys.path`).
For backward compatibility with in-repo hook tests, `user-prompt-submit.py` also
assigns ``_score_pattern_relevance`` / ``_filter_patterns_by_relevance`` to the
same functions (see `tests/test_suite_event1_prompt.py`).

The library module **`omnicursor.prompt_pattern_read`** does **not** duplicate
the algorithm. At import time it loads `prompt_pattern_selection.py` with
`importlib.util.spec_from_file_location`, resolving the path from
`Path(__file__).parents[2]` (OmniCursor repo root). Tests and
`node_cursor_pattern_injection_compute/handler.py` keep importing
`omnicursor.prompt_pattern_read` — behavior matches the hook.

**Layout requirement:** CI and dev checkouts must include `.cursor/hooks/lib/`.
A bare `pip install omnicursor` wheel without the repo tree will not expose this
path; OmniCursor is primarily a **repo + Cursor** product, not an isolated
library wheel for pattern helpers.

---

## 3. Agent routing (multi-strategy scoring) — **intentional duplicate**

**Problem:** `src/omnicursor/agents.py` and `.cursor/hooks/scripts/user-prompt-submit.py`
(or `on_prompt.py`) both implement three-strategy agent scoring so hooks never
import `omnicursor`.

**Status:** Still **duplicated by design**. Mitigations:

- Keep scoring constants (`HARD_FLOOR`, fuzzy thresholds) aligned in comments or
  small shared **markdown** tables in this doc when values change.
- `tests/test_agents.py` and hook integration tests exercise both paths on the
  same prompts where feasible.

**Future (optional):** Extract a **stdlib-only** `lib/agent_routing.py` the same
way as pattern selection, with `agents.py` loading it via `importlib`. That is a
larger refactor; patterns were the first win because the surface area is smaller.

---

## 4. Node contracts (`contract.yaml` + `handler.py`)

Each Cursor-bound node documents:

- `contract.yaml` — ONEX-shaped metadata + `cursor_native` binding to `hooks.json`
- `handler.py` — thin Python surface for tests (`hook_binding()`)

Execution remains the **hook script** path listed in `hooks.json`. See
[`OMNICURSOR_NODE_CONTRACTS.md`](./OMNICURSOR_NODE_CONTRACTS.md).

---

## 5. Related docs

- [`OMNICURSOR_MIGRATION_PLAN.md`](../archive/OMNICURSOR_MIGRATION_PLAN.md) — phases and foundation scope (archived)
- [`MIGRATION_PHASES_HANDOFF.md`](../archive/dev/MIGRATION_PHASES_HANDOFF.md) — port-track checklist (archived)
- [`CURSOR_VS_CLAUDE_HOOKS.md`](../archive/dev/CURSOR_VS_CLAUDE_HOOKS.md) — lifecycle mapping (archived)
- [`CURSOR_FEATURE_SURFACE_MAP.md`](../archive/dev/CURSOR_FEATURE_SURFACE_MAP.md) — capability map (archived)

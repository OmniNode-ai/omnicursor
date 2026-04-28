# OmniCursor Execution Plan

> **Status**: This plan has been fully executed. All tasks below are complete. This file is preserved as a historical record of the build order.

## Completed Phases

### Phase 1 — Python package skeleton (complete)

1. Preserved and rooted the starter-kit rules, docs, prompts, and rubrics
2. Added the package skeleton under `src/omnicursor/`
3. Implemented routing context (`agents.py`) and skill loading (`skills.py`)
4. Added the debugging skill and its rule (`13-systematic-debugging.mdc`)
5. Verified basic imports, tests, and run docs

### Phase 2 — Library modules (complete)

1. Added `check_compliance` with keyword-based registry
2. Added `patterns.py` as a static pattern catalog for preserved rules
3. Ported brainstorming, writing-plans, and plan-ticket as `skills/*.md` (plus additional methodology skills; `adapter-stub` removed from tree)
4. Added 16 agent JSON configs in `.cursor/agents/`

### Phase 3A — Hooks Infrastructure (complete)

1. Created `.cursor/hooks.json` with 4 lifecycle hooks
2. Created `on_prompt.py` — three-strategy scoring (exact/fuzzy/keyword), pattern injection, `systemMessage` enrichment
3. Created `on_shell.py` — two-tier command guard (9 HARD_BLOCK + 11 SOFT_WARN patterns)
4. Created `on_edit.py` — diagnostic `ruff check` on Python edits
5. Created `on_stop.py` — session aggregation with 4-gate outcome classification (failed/success/abandoned/unknown)
6. Created `_common.py` — shared paths, stdin/stdout helpers, event logging, agent config loading
7. Created `pattern_loader.py` — thread-safe in-memory pattern cache loading from `~/.omnicursor/learned_patterns.json`
8. Added `activation_keywords` to all 16 agent JSON configs
9. Upgraded `agents.py` to three-strategy scoring with `HARD_FLOOR = 0.55`, `match_agent_candidates()`, backward-compatible `match_agent()`
10. Ported 8 methodology skills from OmniClaude: pr-review, pr-polish, hostile-reviewer, defense-in-depth, merge-planner, insights-to-plan, handoff, using-git-worktrees
11. Added compliance registry entries for all skills in `skills/` (12 after removing `adapter-stub`)

### Final Verification (complete)

- 120 tests passing
- `ruff check` clean across `src/`, `tests/`, `.cursor/hooks/`
- All hook smoke tests pass
- Library imports cleanly

## What Remains (not yet started)

- Pattern-append UX — enables writing new patterns from sessions
- Seed `~/.omnicursor/learned_patterns.json` — starter patterns for demo
- Valkey/PostgreSQL integration — future performance upgrade, not needed for MVP
- `beforeMCPExecution` / `beforeReadFile` hooks — deferred (Phase 3B)

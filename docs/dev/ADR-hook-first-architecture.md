# ADR: Hook-First Architecture (Rules + Hooks + Library)

**Status:** Accepted (design direction)  
**Context:** OmniCursor Linear **OMN-37**; related **OMN-12**, **OMN-39**, **OMN-44**  
**Scope:** Structured helpers live in `src/omnicursor/` for tests and CI; IDE behavior is rules, hooks, and file-backed skills.

---

## Context

OmniCursor has three behavioral layers:

1. **Cursor Rules** (`.cursor/rules/*.mdc`) — instructions the model sees when keywords match.
2. **Cursor Hooks** (`.cursor/hooks/`) — deterministic, stdlib-only scripts on lifecycle events; see [`CURSOR_VS_CLAUDE_HOOKS.md`](./CURSOR_VS_CLAUDE_HOOKS.md).
3. **Python library** (`src/omnicursor/`) — `get_agent_context`, `SkillRepository`, `check_compliance`, node contracts — **in-process** for pytest and automation.

**Problem statement:** The same **concerns** (routing, compliance, patterns, telemetry) can appear in more than one place. Without explicit ownership, documentation and behavior drift (e.g. two scoring implementations).

---

## Decision

Adopt a **hook-first** default for **lifecycle-triggered, deterministic** work that must run without the model choosing to call anything:

- **Hooks** own: prompt-time classification payload (`systemMessage`), shell gating, edit-time lint signal, stop-time session outcome aggregation, append-only event logging to `~/.omnicursor/events.jsonl`.
- **Rules** own: methodology text, bucket boundaries, keyword activation, and directing the model to read **`skills/*.md`**.
- **Library** owns: **structured** payloads for **tests and CI** (agent context document, skill document, compliance result). Optional: one-off `python -c` for debugging.

**Non-goal:** Replacing rules or hooks with library-only workflows in the IDE.

---

## Ownership table

| Concern | Primary owner | Secondary / duplicate today | Direction |
|---------|---------------|----------------------------|-----------|
| Prompt → agent scoring | Hook: `on_prompt.py` | Library: `agents.py` (same algorithms, `HARD_FLOOR = 0.55`) | **Keep dual path**; document drift risk; optional future: codegen (out of scope) |
| Inject learned patterns | Hook + `pattern_loader.py` | Library: `patterns.py` static list | Hooks **inject**; library **lists** for tests |
| Compliance checking | Library: `check_compliance` | Rules may remind model to self-check | **Library** is authoritative for **machine-checkable** output in CI |
| Skill content | `skills/*.md` (read from disk) | Rules reference paths | **Skills** remain Markdown |
| Dangerous shell commands | Hook: `on_shell.py` | Rules may warn in prose | **Hook** is authoritative for **deny** |
| Post-edit Python quality signal | Hook: `on_edit.py` | Optional CI / local ruff | **Hook** for immediate feedback + logging |
| Session outcome taxonomy | Hook: `on_stop.py` | — | **Hook** |
| Bounded research discipline | Rules: `01-codebase-research.mdc` | Future `beforeReadFile` (Phase 3B) | **Rules** until hook exists |

---

## Duplication risks (explicit)

1. **Scoring** in `on_prompt.py` and `agents.py` — must stay aligned manually until a codegen/shared stub strategy is justified.
2. **Routing narrative** in rules vs what hooks emit — mitigate via this ADR and `CURSOR_VS_CLAUDE_HOOKS.md`.
3. **Compliance** reminders in rules vs `check_compliance` — rubric and tests should favor library checks for verifiable output.

---

## Phased migration

| Phase | Focus | Success criterion |
|-------|--------|-------------------|
| **A (current)** | Hooks + rules + file-backed skills; library for tests | Tests green; hook smoke tests documented |
| **B** | Phase 3B hooks (`beforeMCPExecution`, `beforeReadFile`) if/when available | New hook entries in `hooks.json` + tests |
| **C** | Optional pattern-append UX (script or hook) | Pattern write path + tests |
| **D** | Consolidation pass — trim redundant prose in rules only where hooks/library clearly own the behavior | No behavioral regression; rubric evidence updated |

---

## Consequences

- **Positive:** Cursor-native execution path is obvious (rules + hooks + files).
- **Negative:** Models must **read** skill files explicitly unless a rule embeds the path.
- **Tests:** `tests/test_server.py` exercises the public Python API.

---

## References

- [`CURSOR_VS_CLAUDE_HOOKS.md`](../archive/dev/CURSOR_VS_CLAUDE_HOOKS.md) (archived)
- [`CLAUDE.md`](../../CLAUDE.md), [`DEVELOPER.md`](./DEVELOPER.md), [`HANDOFF.md`](../archive/dev/HANDOFF.md) (archived)
- [`OmniCursor_DoD_Rubric.md`](../archive/root/OmniCursor_DoD_Rubric.md) (archived)

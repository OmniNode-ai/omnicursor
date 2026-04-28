# OmniCursor Handoff Document

**Date**: 2026-04-21
**Purpose**: Enable any developer or AI session to resume implementation without re-reading the entire codebase.

---

## 1. What OmniCursor Is

OmniCursor is a **Cursor-native adaptation of OmniClaude** — rules and hooks in the IDE, plus a **Python library** for tests and CI:

1. **Cursor Rules** (`.cursor/rules/*.mdc`) — always-on and keyword-activated behavioral instructions
2. **Cursor Hooks** (`.cursor/hooks/`) — 4 hook entrypoints in `.cursor/hooks.json`, plus `_common.py` and `pattern_loader.py`
3. **Python library** (`src/omnicursor/`) — `agents`, `skills`, `compliance`, node contracts — **in-process** for tests and tooling

The reference implementation is `omniclaude-main/` (read-only). We selectively adapt its patterns, not mirror it.

---

## 2. Source-of-Truth Hierarchy

When documents disagree:

1. Actual current codebase behavior
2. `cursor.md` — repo conventions and architecture overview
3. `docs/dev/OMNICURSOR_IMPLEMENTATION_BRIEF.md` — implementation decisions
4. `omnicursor-team-guidance.md` — demo-focused guidance with code examples (local / gitignored)
5. `omniclaude-main/` — reference library, never a source of mandatory parity

---

## 3. What Has Been Completed

### Tasks 0–4: Core Infrastructure

- **Task 0** — Full codebase analysis and upgrade path identification
- **Task 1** — `on_prompt.py` enrichment-ready routing: `_score_agent()` returns `(score, reason)`, `classify_prompt()` returns `(agent_name, score, reason)` 3-tuple, `main()` emits `{"systemMessage": "<!-- OmniCursor Agent: ... -->"}`
- **Task 2** — JSON-backed learned pattern loading: `PatternCache` class in `pattern_loader.py`, warms from `~/.omnicursor/learned_patterns.json`, injects up to 5 patterns into `systemMessage`
- **Task 3** — Multi-strategy routing in `agents.py`: exact substring (0.95/0.80), fuzzy SequenceMatcher with length-aware thresholds, keyword overlap (0.55–0.85), `HARD_FLOOR = 0.55`, `match_agent_candidates()` returning top-5 candidates
- **Task 4** — Identical three-strategy scoring ported to `on_prompt.py` hook (hooks cannot import from `src/omnicursor/`, so logic is duplicated)

### Task 5: `activation_keywords` in Agent Configs

Added `activation_keywords` (5 keywords each) to all 16 `.cursor/agents/*.json` files. `polymorphic-agent` intentionally has `[]` (fallback agent). This improves Strategy 3 precision over auto-extraction from trigger text.

### Task 6: Session Outcome Classification

Rewrote `on_stop.py` with `derive_session_outcome(status, events)` using a 4-gate decision tree:
- Gate 1 FAILED: status maps to failure OR error markers in event text
- Gate 2 SUCCESS: work was done AND completion markers present
- Gate 3 ABANDONED: no completion markers AND duration < 60s
- Gate 4 UNKNOWN: insufficient signal

Outcome included in both logged stop event and persisted session summary.

### Task 7: Shell Guard Missing Patterns

Added 2 patterns to `on_shell.py`:
- HARD_BLOCK: `base64 --decode | sh` (obfuscated shell execution) — total now 9
- SOFT_WARN: `eval` execution — total now 11

### Task 8A: Port First 4 Methodology Skills

Created `skills/pr-review.md`, `skills/pr-polish.md`, `skills/hostile-reviewer.md`, `skills/defense-in-depth.md`. Added 4 compliance registry entries (4 checks each). Source: `omniclaude-main/plugins/onex/skills/*/SKILL.md`, adapted for Cursor context.

### Task 8B: Port Remaining 4 Methodology Skills

Created `skills/merge-planner.md`, `skills/insights-to-plan.md`, `skills/handoff.md`, `skills/using-git-worktrees.md`. Added 4 compliance registry entries (4 checks each). Source: same, adapted for Cursor.

### Task 9: Final Verification

- Full `pytest` suite passing (see CI)
- `ruff check` clean across `src/`, `tests/`, `.cursor/hooks/`
- All hook smoke tests pass
- Library imports cleanly (`agents`, `skills`, `compliance`)
- 4 unused imports cleaned up (pre-existing lint, not regressions)

### Task 10: Local Pre-Commit Gate + CI Trigger Policy

- Added shared git hook at `.githooks/pre-commit`.
- Hook runs CI-parity checks before commit:
	- `ruff check src/ tests/ .cursor/hooks/`
	- `pytest tests/ -v`
	- skill compliance coverage validation
- Repository setup now enables shared hooks via `git config core.hooksPath .githooks` and `chmod +x .githooks/pre-commit`.
- GitHub Actions CI trigger is now pull-request based for `main` (no direct `push` trigger in `.github/workflows/ci.yml`).

---

## 4. Current State of All Files

### Hooks (`.cursor/hooks/`, stdlib only)

| File | Event | Behavior |
|------|-------|----------|
| `on_prompt.py` | `beforeSubmitPrompt` | Three-strategy scoring (exact/fuzzy/keyword), `HARD_FLOOR=0.55`, pattern injection from JSON cache, emits `{"systemMessage": ...}` |
| `pattern_loader.py` | (imported by on_prompt) | Thread-safe `PatternCache` singleton, warms from `~/.omnicursor/learned_patterns.json` |
| `on_shell.py` | `beforeShellExecution` | 9 HARD_BLOCK + 11 SOFT_WARN regex patterns, two-tier deny/warn/allow |
| `on_edit.py` | `afterFileEdit` | Diagnostic `ruff check` on `.py` files, logs to `events.jsonl` |
| `on_stop.py` | `stop` | Aggregates session events, 4-gate outcome classification (failed/success/abandoned/unknown), writes session summary |
| `_common.py` | Shared | Paths (incl. `LEARNED_PATTERNS_FILE`), stdin/stdout, event logging, agent config loading |

### Python library (`src/omnicursor/`)

| Module | Notes |
|--------|-------|
| `agents.py` | Three-strategy scoring, `HARD_FLOOR=0.55`, `get_agent_context()`, dynamic JSON loading from `.cursor/agents/*.json` |
| `compliance.py` | Registry for all skills, 3–5 keyword checks each |
| `skills.py` | Auto-discovers `skills/*.md` |
| `schemas.py` | `AgentContext`, `SkillDocument`, `ComplianceResult`, `PatternRecord`, `DatabaseStatus` |
| `node_contracts.py` | Cursor-native `contract.yaml` discovery / validation |
| `db.py` | Repo path constants, `InMemoryDatabase` placeholder |
| `patterns.py` | Lists 4 preserved rules as `PatternRecord` objects (static) |

### Agent Configs (`.cursor/agents/*.json`, 16 files)

Schema: `name`, `description`, `category`, `activation_patterns` (`explicit_triggers`, `context_triggers`, `activation_keywords`), `instructions`, `recommended_skill`.

All 16 configs have `activation_keywords` (5 each, except `polymorphic-agent` which has `[]`).

### Skills (`skills/*.md`, 13 files)

Original (4) plus ports: `systematic-debugging`, `brainstorming`, `writing-plans`, `plan-ticket`, and ported OmniClaude methodology skills (`pr-review`, `handoff`, etc.). **`adapter-stub` removed** — Bucket 3 remains documented only in `docs/ARCHITECTURE.md`.

Ported from OmniClaude (8): `pr-review`, `pr-polish`, `hostile-reviewer`, `defense-in-depth`, `merge-planner`, `insights-to-plan`, `handoff`, `using-git-worktrees`

### Tests

All tests passing. `pytest tests/ -v` is fast (~sub-second on typical hardware).

---

## 5. Demo Success Criteria (from team guidance)

| # | What to Show | Status |
|---|-------------|--------|
| 1 | Prompt auto-routed to correct agent via hook | **Done** — `on_prompt.py` emits agent + confidence + reason via `systemMessage` |
| 2 | File edit auto-linted without user action | **Done** — `on_edit.py` runs diagnostic ruff |
| 3 | Pattern from session A appears in session B | **Partial** — `learned_patterns.json` persists and is injected via `pattern_loader.py`. Missing: ergonomic writer (e.g. script or hook) for new patterns |
| 4 | Hooks disabled, system still usable | **Done** — rules + `skills/*.md` + library for tests |

---

## 6. What Remains

### Port track (agents, skills, ONEX nodes & contracts)

Use **`docs/dev/MIGRATION_PHASES_HANDOFF.md`** as the checklist. In short:

- **Agents** — keep JSON agents + routing tests green; add configs **only when** a new workflow needs them (omniclaude is reference, not a full port list).
- **Skills** — maintain `skills/*.md` + `compliance.py` + rules; add skills incrementally (~12–17 curated is the default ceiling unless the team widens scope).
- **Nodes** — evolve `src/omnicursor/nodes/*` when a contract or demo requires it; no mandate to mirror omniclaude’s full node catalog.

This track **does not** include Kafka daemon work, Linear-in-hooks Phase 6, omnimarket MCP, or authoritative pattern DB writes — see **`docs/OMNICURSOR_MIGRATION_PLAN.md`** for those.

### Other tracks (outside the port checklist)

| Item | Priority | Description |
|------|----------|-------------|
| Pattern writer UX / PG | Varies | Persistence track — append or store patterns; completes richer demo criterion 3 when owned |
| Seed `learned_patterns.json` | Medium | Optional demo data |
| Hooks Phase 6 (Linear, DoD in hooks) | Varies | Hooks + rules track per migration plan |
| Kafka / emit daemon (Phase 5) | Varies | Infra / team bus |
| Omnimarket MCP bridge | Sponsor | Integration track |
| Valkey integration | Deferred | Performance upgrade |
| `beforeMCPExecution` / `beforeReadFile` hooks | Deferred | Phase 3B — not needed for MVP |

---

## 7. Key Constraints

- `omniclaude-main/` is **read-only** — never modify
- `.cursor/rules/*.mdc` are teaching artifacts — modify with care
- Hooks use **Python stdlib only** (`difflib.SequenceMatcher` is stdlib; `yaml` is not)
- All hooks exit 0 (except `on_shell.py` deny)
- `pyproject.toml` deps stay minimal: `pydantic`, `pyyaml`
- No Kafka, Qdrant, Slack, PostgreSQL, or Valkey as dependencies

---

## 8. Known Ambiguities

1. **Prompt enrichment may not work.** `on_prompt.py` emits `{"systemMessage": ...}` but Cursor documentation is unclear on whether `beforeSubmitPrompt` output is consumed. The Implementation Brief says: treat this as a capability gate, not a design reset.

2. **Scoring logic is duplicated.** `_score_agent()` exists in both `on_prompt.py` (hooks, stdlib) and `agents.py` (library). They are aligned (identical 3-strategy logic) but must stay in sync manually. Hooks cannot import from `src/omnicursor/`.

---

## 9. Running the Project

```bash
# Setup
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit

# Tests
pytest tests/ -v

# Lint
ruff check src/ tests/ .cursor/hooks/

# Smoke test on_prompt.py
echo '{"prompt": "debug this error in my code"}' | python3 .cursor/hooks/on_prompt.py

# Smoke test on_shell.py
echo '{"command": "rm -rf /"}' | python3 .cursor/hooks/on_shell.py

# Smoke test on_stop.py
echo '{"conversation_id": "test-123", "status": "completed"}' | python3 .cursor/hooks/on_stop.py

```

---

## 10. How to Build Context for a New Session

Paste this as a preamble:

```
Read these files to build working context:
- cursor.md (conventions and architecture overview)
- docs/dev/HANDOFF.md (current state and remaining tasks)
- docs/dev/MIGRATION_PHASES_HANDOFF.md (port track: agents, skills, nodes — if that is your scope)
- docs/dev/OMNICURSOR_IMPLEMENTATION_BRIEF.md (implementation decisions)
- omnicursor-team-guidance.md (demo-focused guidance)
- .cursor/hooks/on_prompt.py, _common.py, pattern_loader.py, on_shell.py, on_stop.py
- src/omnicursor/agents.py, compliance.py, skills.py
```

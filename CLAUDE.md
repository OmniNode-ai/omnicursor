# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit

# Tests
pytest tests/ -v              # full suite
pytest tests/test_agents.py -v  # single file
pytest tests/ -k "test_debug"   # by name pattern

# Lint
ruff check src/ tests/ .cursor/hooks/
```

## Local pre-commit gate

- Shared hook path: `.githooks/pre-commit`
- Runs the same checks as CI before commit:
	- `ruff check src/ tests/ .cursor/hooks/`
	- `pytest tests/ -v`
	- skill compliance coverage validation
- Emergency bypass only: `git commit --no-verify`
- GitHub Actions CI is pull-request based for `main`; rely on local pre-commit checks before opening PRs.

## Architecture

OmniCursor is **Cursor-native**: **rules** + **hooks** define IDE behavior. A **Python library** under `src/omnicursor/` supports **tests**, **CI**, and optional scripting.

1. **Cursor Rules** (`.cursor/rules/`, 11 `.mdc` files) — behavior surface. Rules `00`–`02` are always-on; `10`–`17` activate on keyword match (`16` / `17` = Linear create / consume). Rules direct the model to read **`skills/*.md`** and to use hook-injected routing when present.
2. **Cursor Hooks** (`.cursor/hooks/`) — 4 hook entrypoints in `.cursor/hooks.json`, plus `_common.py` and `pattern_loader.py`. Deterministic lifecycle scripts, stdlib only, no LLM. Each hook is described by an **OmniClaude-shaped node contract** in `src/omnicursor/nodes/*/contract.yaml`; see `docs/dev/OMNICURSOR_NODE_CONTRACTS.md` and `omnicursor.node_contracts`. For how OmniClaude-style logic is shared (or intentionally duplicated) between hooks and `src/omnicursor/`, read **`docs/dev/OMNICLAUDE_TO_CURSOR_PORT.md`**.
3. **Python library** (`src/omnicursor/`) — `get_agent_context`, `SkillRepository`, `check_compliance`, and schemas — for **tests and automation**.

### Agent routing — two merge layers + three-strategy scoring

`agents.py` merges hardcoded `AGENT_CONTEXTS` (4 categories: debugging, brainstorming, planning, ticketing) with dynamically loaded JSON from `.cursor/agents/*.json` (17 configs). JSON overlays hardcoded via `{**AGENT_CONTEXTS, **_JSON_AGENTS}`. The `ALIASES` dict maps shorthand names to canonical categories.

Both `on_prompt.py` and `agents.py` use identical three-strategy scoring:

1. **Exact substring match** on `explicit_triggers` / `context_triggers` → 0.95 / 0.80 confidence.
2. **Fuzzy match** via `SequenceMatcher` with length-aware thresholds (0.7 for long triggers, 0.8 for short).
3. **Keyword overlap** on `activation_keywords` → scaled to 0.55–0.85 range.

`HARD_FLOOR = 0.55` — candidates below this are discarded. No match returns `DEFAULT_CONTEXT` / polymorphic-agent fallback.

### Hook execution model

| Hook | Event | Behavior |
|------|-------|----------|
| `on_prompt.py` | `beforeSubmitPrompt` | Classifies prompt → emits `{"systemMessage": ...}` with agent + confidence + learned patterns (whether Cursor consumes this output is a platform uncertainty) |
| `on_shell.py` | `beforeShellExecution` | Two-tier guard: 9 HARD_BLOCK patterns (deny), 11 SOFT_WARN patterns (allow + warning) |
| `on_edit.py` | `afterFileEdit` | Runs `ruff check` diagnostically on `.py` files — never `--fix`, never modifies |
| `on_stop.py` | `stop` | Aggregates session events, classifies outcome (failed/success/abandoned/unknown) via 4-gate decision tree |
| `pattern_loader.py` | (library) | Thread-safe in-memory pattern cache, loads from `~/.omnicursor/learned_patterns.json` |

- Only `on_shell.py` can block execution via `{"permission": "deny"}`.
- All other hooks are informational — Cursor ignores their stdout. They log to `~/.omnicursor/events.jsonl`.
- All hooks communicate via stdin/stdout JSON and use **stdlib only**.

### Session outcome classification (`on_stop.py`)

`derive_session_outcome(status, events)` uses a 4-gate decision tree:
- **Gate 1 — Failed**: status maps to failure OR error markers (traceback, exception, test failures) in event text.
- **Gate 2 — Success**: work was done (file edits, prompt classifications) AND completion markers present.
- **Gate 3 — Abandoned**: no completion markers AND session duration < 60 seconds.
- **Gate 4 — Unknown**: ambiguous signals (catch-all).

### Skills (16 total)

| Skill | Bucket | Source |
|-------|--------|--------|
| `systematic-debugging` | 1 | Original |
| `brainstorming` | 1 | Original |
| `writing-plans` | 1 | Original |
| `plan-ticket` | 3 | Original (upgraded to Linear MCP) |
| `pr-review` | 1 | Ported from OmniClaude |
| `pr-polish` | 1 | Ported from OmniClaude |
| `hostile-reviewer` | 1 | Ported from OmniClaude |
| `defense-in-depth` | 1 | Ported from OmniClaude |
| `merge-planner` | 1 | Ported from OmniClaude |
| `insights-to-plan` | 1 | Ported from OmniClaude |
| `handoff` | 1 | Ported from OmniClaude |
| `using-git-worktrees` | 1 | Ported from OmniClaude |
| `recap` | 1 | Original |
| `plan-review` | 1 | Original |
| `plan-to-tickets` | 3 | Original (Linear MCP) |
| `execute-plan` | 3 | Original (Linear MCP + autonomous pipeline) |

### 3-bucket classification (from Cursor rules)

- **Bucket 1** (systematic-debugging, brainstorming, writing-plans, pr-review, pr-polish, hostile-reviewer, defense-in-depth, merge-planner, insights-to-plan, handoff, using-git-worktrees, recap, plan-review): pure methodology, no external calls.
- **Bucket 2**: (unused — formerly plan-ticket YAML-only mode)
- **Bucket 3** (plan-ticket, plan-to-tickets, execute-plan): Linear MCP integration via `tracker.*` tools. Requires Linear MCP configured in `~/.cursor/mcp.json`.

### Smoke-check registry (`compliance.py`)

`COMPLIANCE_REGISTRY` maps each of the 16 skills to 3–5 keyword/phrase checks. `check_compliance(skill_name, response_summary)` returns a `ComplianceResult` with per-check pass/fail. These are **vocabulary smoke-checks** (does the response use the right terminology?), not behavioral compliance — a well-worded response can pass without doing real work. Renamed to "smoke-check" in docs; function/class names kept for API stability.

## Key constraints

- `omniclaude-main/` is a **read-only reference** — never modify it.
- `.cursor/rules/*.mdc` are teaching artifacts — modify with care.
- Hooks must use **Python stdlib only** (no pip dependencies).
- `on_edit.py` runs `ruff check` diagnostically — never `--fix`, never modifies files.
- `schemas.py` defines 5 Pydantic v2 models: `AgentContext`, `SkillDocument`, `ComplianceResult`, `PatternRecord`, `DatabaseStatus`. The agents, skills, and compliance modules depend on these models.
- When adding a new agent: create `.cursor/agents/<name>.json` with `name`, `description`, `category`, `activation_patterns` (must include `explicit_triggers`, `context_triggers`, and `activation_keywords`), `instructions`, `recommended_skill`. It auto-loads on startup.
- When adding a new skill: create `skills/<name>.md` AND copy it to `.cursor/skills/<name>/SKILL.md` (both paths are required — CI scans `skills/*.md`, `SkillRepository` loads from `.cursor/skills/<name>/SKILL.md`). Add a smoke-check entry in `compliance.py` with 3–5 keyword/phrase checks. Update the expected sets in `tests/test_compliance.py` and `tests/test_skills.py`.
- **Port track** (agents, skills, ONEX nodes & contracts from OmniClaude): `docs/dev/MIGRATION_PHASES_HANDOFF.md`. Hooks, Kafka, Linear-in-hooks, MCP bridge, and authoritative pattern writes are covered in `docs/OMNICURSOR_MIGRATION_PLAN.md` / other tracks.

## Omnimarket bridge

OmniCursor invokes **omnimarket** nodes as the primary bridge to OmniNode — not direct omniintelligence service APIs.

### Locating the checkout

- Set `OMNIMARKET_ROOT` to the absolute path of a local omnimarket checkout.
- If `OMNIMARKET_ROOT` is unset, bridge code may fall back to `omnimarket-main/` in the repo root as a **dev convenience only**.
- Omnimarket is **never cloned from GitHub at runtime**. The checkout must already exist locally.

### Invocation

- **Preferred:** `python -m omnimarket.nodes.<node_name>` via subprocess (e.g. `python -m omnimarket.nodes.node_local_review --dry-run`). The bridge injects `{OMNIMARKET_ROOT}/src` into `PYTHONPATH` for the subprocess because omnimarket uses a `src/` layout.
- **Fallback:** In-process handler import — only if the subprocess path is blocked.
- **Out of scope:** `onex run <contract.yaml>` (broken upstream routing validation) and direct HTTP calls to omniintelligence reducers/orchestrators/quality-scoring services.

### Docker

`compose.yaml` is approved as-is for local infra (Postgres, Redpanda, Valkey, intelligence services). It is **not** the primary bridge path — prefer local subprocess invocation of omnimarket nodes. Do not expand Docker Compose for bridge work.

### Patterns

Pattern **writes** stay local (file + team-owned PostgreSQL). Bridging pattern writes to upstream intelligence is **out of capstone scope** (year-2). Optional `OMNICURSOR_PATTERN_SYNC_HTTP` exists for dev experimentation only (default off).

## Source-of-truth hierarchy

When documents disagree, use this order:

1. Actual current codebase behavior
2. This file (`CLAUDE.md`) — repo conventions and architecture overview
3. `docs/dev/OMNICURSOR_IMPLEMENTATION_BRIEF.md` — implementation decisions
4. `omnicursor-team-guidance.md` — demo-focused guidance (local; gitignored)
5. `omniclaude-main/` — read-only reference library

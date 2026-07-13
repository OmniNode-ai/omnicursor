# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and Cursor agents when
working in this repository. It is the **auto-loaded entry point** and the top of the
documentation source-of-truth hierarchy (after the actual code). For the full doc map
see [`docs/INDEX.md`](docs/INDEX.md).

## What OmniCursor is

OmniCursor is a **Cursor-native** plugin that ports OmniClaude's methodology to Cursor:
behavior lives in **rules**, **hooks**, **skills**, and **agent configs**, backed by a
Python library under `src/omnicursor/` used for **tests, CI, the MCP server, and the
shared logic the hooks delegate to**. The core runs fully **offline**; intelligence and
event-emission tiers are opt-in. Full architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Current status & known drift: [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md).

## Commands

```bash
# Setup (Python 3.10+; CI standardizes on 3.12)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" ruff          # [dev] is pytest-only; ruff is a separate dep
git config core.hooksPath .githooks   # wire the shared pre-commit gate

# Tests (640 tests across 24 test modules)
pytest tests/ -v                      # full suite
pytest tests/test_agents.py -v        # single file
pytest tests/ -k "debug"              # by name pattern

# Lint
ruff check src/ tests/ .cursor/hooks/
```

`requires-python = ">=3.10"` — the code uses PEP 604 `X | None` syntax, so Python 3.9
cannot even collect the suite. Optional extra: `.[mcp]` for the omnimarket MCP server.

## Local pre-commit gate (`.githooks/pre-commit`)

Runs the same checks as CI, in order:

1. `ruff check src/ tests/ .cursor/hooks/`
2. `pytest tests/ -v`
3. **Skill-compliance coverage** — every `skills/*.md` (excluding `README.md`) must have
   an entry in `src/omnicursor/compliance.py`.

Emergency bypass only: `git commit --no-verify`. CI (`.github/workflows/ci.yml`) runs the
same checks on Python 3.12 — plus mypy, bandit, detect-secrets (baseline compare), offline
link check, the A10.7 plugin gates (`scripts/ci/`: manifest/MCP, frontmatter+category,
topic-literal, hook stdlib-only), shellcheck, and a sibling-drift job that checks out the
public `omnimarket`/`omnibase_core` repos so the registry/canonical-event tests actually
run — on **pull requests to `main` and pushes to `main`**. Branch protection should
require the aggregate `ci-summary` job.

## Architecture (overview — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for depth)

Four behavior surfaces + one library:

1. **Rules** (`.cursor/rules/`, 14 `.mdc`) — rules `00`–`03` are always-on; `10`+ activate
   on keyword match. Rules direct the model to read `skills/*.md` and to use hook-injected
   routing when present.
2. **Hooks** (`.cursor/hooks/`) — 7 lifecycle events wired in `.cursor/hooks.json`, scripts
   under `.cursor/hooks/scripts/`, shared logic under `.cursor/hooks/lib/`. Deterministic,
   no LLM. Each event is described by an OmniClaude-shaped **node contract**
   (`src/omnicursor/nodes/*/contract.yaml`). See the hook table below.
3. **Skills** (17) — dual-located (see "Adding a skill").
4. **Agents** (`.cursor/agents/`, 17 JSON configs) — routing profiles.
5. **Python library** (`src/omnicursor/`) — `get_agent_context`, `SkillRepository`,
   `check_compliance`, the scoring engine, node-contract discovery, and schemas. The single
   source of truth for the logic the hooks delegate to.

### Hooks

| Script (`.cursor/hooks/scripts/`) | Event | Behavior |
|---|---|---|
| `session-start.py` | `sessionStart` | Session init + best-effort daemon-ensure + emit `session-started`. **Injects** session-level context (baseline patterns + delegation rule + prior session) via `additional_context` — Cursor's real injection channel. |
| `user-prompt-submit.py` | `beforeSubmitPrompt` | Classify prompt → emit agent + confidence + relevant patterns for backend learning. **Block/observe-only** (`{continue, user_message}`); returns `{"continue": true}`. Does **not** inject — Cursor ignores `systemMessage` here. |
| `shell-guard.py` | `beforeShellExecution` | **Only** hook that can deny. Returns `{permission: allow\|deny\|ask, user_message, agent_message}`. Two tiers: **9 HARD_BLOCK** (deny), **12 SOFT_WARN** (allow + warn). Optional config-gated DoD/dispatch deny tiers, off by default. |
| `post-edit.py` | `afterFileEdit` | Diagnostic only: `ruff check` on `.py`, `tsc --noEmit` on `.ts`/`.tsx`; emit `tool-executed`. **Never `--fix`, never modifies files.** |
| `post-tool-use.py` | `postToolUse` | **Refreshes** injected context via `additional_context` (patterns for the domain inferred from the tool's file path); emit `tool-executed`. |
| `stop.py` | `stop` | Aggregate session events → outcome (`failed`/`success`/`abandoned`/`unknown`) via a 4-gate decision tree; write durable `~/.omnicursor/outbox.jsonl`. Loop-end signal. |
| `session-end.py` | `sessionEnd` | Emit `session-ended` (true conversation close; complements `stop`'s loop-end). Fire-and-forget. |

**Injection reality:** Cursor exposes exactly two live injection channels —
`sessionStart.additional_context` (initial) and `postToolUse.additional_context`
(refresh). `beforeSubmitPrompt` is block-only and CANNOT inject; per-prompt routing is
emitted for backend learning, not injected. Shared context-assembly lives in
`.cursor/hooks/lib/context_injection.py`.

Active scripts are **stdlib-only** (no pip dependencies): they insert `.cursor/hooks/lib/`
(and `src/` where needed) on `sys.path` and delegate to first-party helpers
(`_common`, `context_injection`, `emit_client`, and `omnicursor.*` for `shell_guard` /
`file_edit` / `session_outcome`), the single source of truth — do not duplicate logic in
the scripts. All hooks log to `~/.omnicursor/events.jsonl` and emit best-effort events via
the shared emit daemon; only `shell-guard` can return `{"permission": "deny"}`.

### Agent routing

`agents.py` merges 4 hardcoded `AGENT_CONTEXTS` categories (debugging, brainstorming,
planning, ticketing) with the 17 JSON configs via `{**AGENT_CONTEXTS, **_JSON_AGENTS}`
(JSON wins on collision); `ALIASES` maps shorthand → canonical. Both the hook and
`agents.py` share one engine in `scoring.py`: a **4-stage scorer** — exact explicit-trigger
(0.95), exact context-trigger (0.80), length-aware fuzzy via `SequenceMatcher` (explicit
triggers only), and keyword overlap (scaled 0.55–0.85) — with `HARD_FLOOR = 0.55`. No match
falls back to `omnicursor-generalist` (library `DEFAULT_CONTEXT`) / `polymorphic-agent`
(hook runtime). Exact thresholds live in `src/omnicursor/scoring.py` and
[`docs/ARCHITECTURE.md` §5](docs/ARCHITECTURE.md#5-agent-routing).

### Skills & the 3-bucket model

17 skills, canonical id `onex-<slug>`. The 3 buckets (defined in rule
`00-omninode-concepts.mdc`): **1** pure methodology (no external calls), **2** local-data
hybrid (reads bounded local files, no external calls), **3** external integration (Linear
MCP / Kafka / validators). Subtlety to preserve: the **rule** `12-plan-ticket` is Bucket 2
(emits a local YAML ticket template, no calls) while the **skill** `onex-plan-ticket` it
points to is Bucket 3 (adds a Linear MCP step). `onex-plan-to-tickets` and
`onex-execute-plan` are also Bucket 3. Full skill table: [`docs/ARCHITECTURE.md` §2–§3](docs/ARCHITECTURE.md).

Compliance: `src/omnicursor/compliance.py` maps all 17 skills (3–5 checks each). These are
**vocabulary smoke-checks**, not behavioral verification; `check_compliance` accepts a bare
slug or a canonical id.

## Key constraints

- `omniclaude-main/` is a **read-only reference** — never modify it (gitignored; absent from
  a clean clone).
- Hooks must use **Python stdlib only** (no pip dependencies in hook code paths); delegate
  logic to `omnicursor.*`, don't duplicate it.
- `post-edit.py` is **diagnostic only** — never `--fix`, never writes files.
- `.cursor/rules/*.mdc` are teaching artifacts — modify with care.
- `schemas.py` defines 5 Pydantic v2 models: `AgentContext`, `SkillDocument`,
  `ComplianceResult`, `PatternRecord`, `DatabaseStatus`.

### Adding an agent

Create `.cursor/agents/<name>.json` with `name`, `description`, `category`,
`activation_patterns` (must include `explicit_triggers`, `context_triggers`,
`activation_keywords`), `instructions`, and `recommended_skill` (use `onex-<slug>`). It
auto-loads on startup.

### Adding a skill (dual-path — both files required)

1. `skills/<slug>.md` (CI scans `skills/*.md`).
2. `.cursor/skills/onex-<slug>/SKILL.md` (`SkillRepository` loads from here).
3. Add a 3–5 check entry in `src/omnicursor/compliance.py`.
4. Update the expected sets in `tests/test_compliance.py` and `tests/test_skills.py`.

## OmniMarket bridge (opt-in)

The bridge invokes **omnimarket** nodes as the path to OmniNode
(`src/omnicursor/omnimarket_bridge.py`; MCP server at
`src/omnicursor/mcp/omnimarket_bridge_server.py`).

- Set `OMNIMARKET_ROOT` to a local omnimarket checkout; if unset, the bridge falls back to
  `omnimarket-main/` in the repo root (dev convenience only). **Never cloned at runtime.**
- Invocation: `python -m omnimarket.nodes.<node>` via subprocess, with `{OMNIMARKET_ROOT}/src`
  prepended to `PYTHONPATH`. Override the interpreter with `OMNIMARKET_PYTHON`.
- Env: `OMNICURSOR_PATTERN_SYNC_HTTP` (optional pattern pull, **default off**),
  `OMNICURSOR_EMIT_SOCKET` (event socket, default `~/.omnicursor/emit.sock`).
- `compose.yaml` is local infra (Postgres/Redpanda/Valkey/intelligence) — **not** the
  primary bridge path; prefer subprocess invocation. Pattern writes stay local; bridging
  them upstream is out of scope.

## Source-of-truth hierarchy

When documents disagree, trust in this order:

1. **Actual current codebase behavior**
2. **`CLAUDE.md`** (this file) — agent operating contract / orientation
3. The docs under `docs/` — architecture (`ARCHITECTURE.md`) & current state (`CURRENT_STATE.md`)
4. `omnicursor-team-guidance.md` — demo-focused guidance (local; gitignored)
5. `omniclaude-main/` — read-only reference library (gitignored; absent from a clean clone)

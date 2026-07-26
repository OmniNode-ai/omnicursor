# CLAUDE.md

Auto-loaded entry point for Claude Code and Cursor agents; top of the doc
source-of-truth hierarchy (after the actual code). Doc map: [`docs/INDEX.md`](docs/INDEX.md).

## What OmniCursor is

A **Cursor-native** plugin porting OmniClaude's methodology to Cursor: behavior lives in
**rules**, **hooks**, **skills**, and **agent configs**, backed by a Python library under
`src/omnicursor/` (tests, CI, the MCP server, the shared logic hooks delegate to). The
core runs fully **offline**; intelligence and event-emission tiers are opt-in.
Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Status & known drift:
[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md).

## Commands

```bash
# Setup (requires-python >=3.10 — PEP 604 unions, so 3.9 can't even collect; CI uses 3.12)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" ruff          # [dev] is pytest-only; ruff is a separate dep
git config core.hooksPath .githooks   # wire the shared pre-commit gate

# Tests (counts drift — regenerate with: pytest tests/ --collect-only -q | tail -1)
pytest tests/ -v                      # main suite; node suites: pytest src/omnicursor/nodes
pytest tests/ -k "debug"              # by name pattern

# Lint (same scope as the gate and CI — scripts/ci/ is included)
ruff check src/ tests/ .cursor/hooks/ scripts/ci/
ruff format --check src/ tests/ .cursor/hooks/ scripts/ci/
```

Optional extra: `.[mcp]` for the omnimarket MCP server.

## Local pre-commit gate (`.githooks/pre-commit`)

Five steps (the hook script is the source of truth): `ruff check` + `ruff format --check`
(scope above), full `pytest tests/ -v`, **skill-compliance coverage** (every `skills/*.md`
except `README.md` needs an entry in `src/omnicursor/compliance.py`), and the **A10.7
plugin gates** (`scripts/ci/`: manifest validated against the pinned official
cursor/plugins schema in `schemas/`, frontmatter+category, topic-literal, hook
stdlib-only). Emergency bypass only: `git commit --no-verify`.

CI (`.github/workflows/ci.yml`) runs the same on Python 3.12 with `.[dev,mcp]`, plus
mypy, bandit, detect-secrets (baseline compare), offline link check, MCP wiring,
shellcheck, and a sibling-drift job that checks out `omnimarket`/`omnibase_core` at
governed pin SHAs (the weekly scheduled run probes the moving `dev` heads instead).
Triggers: PRs to `main`, pushes to `main`, `workflow_dispatch`, weekly schedule. Fork PRs
need a maintainer's "Approve and run" (see the trigger comment in `ci.yml`). Branch
protection should require the aggregate `ci-summary` job — as of 2026-07-26 `main` has
no branch protection at all, so verify live before relying on it.

## Architecture (overview — depth in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md))

Four behavior surfaces + one library:

1. **Rules** (`.cursor/rules/`, 14 `.mdc`) — `00`–`03` always-on; `10`+ activate on
   keyword match. Rules direct the model to read `skills/*.md` and to use hook-injected
   routing when present.
2. **Hooks** (`.cursor/hooks/`) — 7 lifecycle events wired in `.cursor/hooks.json`,
   scripts under `scripts/`, shared logic under `lib/`. Deterministic, no LLM. Each event
   has an OmniClaude-shaped node contract (`src/omnicursor/nodes/*/contract.yaml`).
3. **Skills** (17) — dual-located (see "Adding a skill").
4. **Agents** (`.cursor/agents/`, 17 JSON configs) — routing profiles.
5. **Python library** (`src/omnicursor/`) — `get_agent_context`, `SkillRepository`,
   `check_compliance`, the scoring engine, node-contract discovery, and schemas
   (`schemas.py`: 5 Pydantic v2 models). Single source of truth for hook logic.

### Hooks

| Script (`.cursor/hooks/scripts/`) | Event | Behavior |
|---|---|---|
| `session-start.py` | `sessionStart` | Init + best-effort daemon-ensure + emit. **Injects** session context via `additional_context`. |
| `user-prompt-submit.py` | `beforeSubmitPrompt` | Classify prompt → emit agent + confidence + patterns for backend learning. **Block/observe-only**; returns `{"continue": true}`. Does **not** inject. |
| `shell-guard.py` | `beforeShellExecution` | **Only** hook that can deny (`{permission: allow\|deny\|ask, ...}`). Tiers: **9 HARD_BLOCK** (deny), **12 SOFT_WARN** (allow + warn); config-gated DoD/dispatch deny tiers, off by default. |
| `post-edit.py` | `afterFileEdit` | Diagnostic only: `ruff check` on `.py`, `tsc --noEmit` on `.ts`/`.tsx`. **Never `--fix`, never modifies files.** |
| `post-tool-use.py` | `postToolUse` | **Refreshes** injected context via `additional_context` (domain inferred from the tool's file path). |
| `stop.py` | `stop` | Aggregate events → outcome (`failed`/`success`/`abandoned`/`unknown`) via a 4-gate tree; write durable `~/.omnicursor/outbox.jsonl`. Loop-end signal. |
| `session-end.py` | `sessionEnd` | Emit `session-ended` (true conversation close). Fire-and-forget. |

**Injection reality:** Cursor exposes exactly two live injection channels —
`sessionStart.additional_context` (initial) and `postToolUse.additional_context`
(refresh). `beforeSubmitPrompt` is block-only and CANNOT inject; per-prompt routing is
emitted for backend learning, not injected. Shared context-assembly lives in
`.cursor/hooks/lib/context_injection.py`.

Active scripts are **stdlib-only**: they insert `.cursor/hooks/lib/` (and `src/` where
needed) on `sys.path` and delegate to first-party helpers — never duplicate logic in the
scripts. All hooks log to `~/.omnicursor/events.jsonl` and emit best-effort events via
the shared emit daemon.

### Agent routing

`agents.py` merges 4 hardcoded `AGENT_CONTEXTS` categories (debugging, brainstorming,
planning, ticketing) with the 17 JSON configs via `{**AGENT_CONTEXTS, **_JSON_AGENTS}`
(JSON wins on collision); `ALIASES` maps shorthand → canonical. Hook and library share one
engine in `scoring.py`: a 4-stage scorer (exact explicit-trigger, exact context-trigger,
length-aware fuzzy on explicit triggers only, keyword overlap) with `HARD_FLOOR = 0.55`.
No match falls back to `omnicursor-generalist` (library `DEFAULT_CONTEXT`) /
`polymorphic-agent` (hook runtime). Exact thresholds: `src/omnicursor/scoring.py` and
[`docs/ARCHITECTURE.md` §5](docs/ARCHITECTURE.md#5-agent-routing).

### Skills & the 3-bucket model

17 skills, canonical id `onex-<slug>`. Buckets (rule `00-omninode-concepts.mdc`):
**1** pure methodology, **2** local-data hybrid (bounded local reads), **3** external
integration (Linear MCP / Kafka / validators). Subtlety to preserve: the **rule**
`12-plan-ticket` is Bucket 2 (emits a local YAML ticket template, no calls) while the
**skill** `onex-plan-ticket` it points to is Bucket 3 (adds a Linear MCP step);
`onex-plan-to-tickets` and `onex-execute-plan` are also Bucket 3. Full skill table:
[`docs/ARCHITECTURE.md` §3](docs/ARCHITECTURE.md).

Compliance: `src/omnicursor/compliance.py` maps all 17 skills (3–5 checks each) —
**vocabulary smoke-checks**, not behavioral verification; `check_compliance` accepts a
bare slug or a canonical id.

## Key constraints

- Sibling reference checkouts (`omniclaude/`, `omnimarket/`, `omnimarket-main/`,
  `omnidash/`, `omnidash-main/` — see `.gitignore`) are **read-only, local-only** — never
  modify or commit them. Note: `omniclaude-main/` is NOT in `.gitignore`; use
  `omniclaude/` for a reference clone or it will be tracked.
- Hooks must use **Python stdlib only** (no pip dependencies in hook code paths);
  delegate logic to `omnicursor.*`, don't duplicate it.
- `post-edit.py` is **diagnostic only** — never `--fix`, never writes files.
- `.cursor/rules/*.mdc` are teaching artifacts — modify with care.

### Adding an agent

Create `.cursor/agents/<name>.json` (copy an existing config): `activation_patterns`
must include `explicit_triggers`, `context_triggers`, `activation_keywords`;
`recommended_skill` uses `onex-<slug>`. Auto-loads on startup.

### Adding a skill (dual-path — both files required)

1. `skills/<slug>.md` (CI scans `skills/*.md`).
2. `.cursor/skills/onex-<slug>/SKILL.md` (`SkillRepository` loads from here).
3. Add a 3–5 check entry in `src/omnicursor/compliance.py`.
4. Update the expected sets in `tests/test_compliance.py` and `tests/test_skills.py`.

## OmniMarket bridge (opt-in)

The bridge invokes **omnimarket** nodes as the path to OmniNode
(`src/omnicursor/omnimarket_bridge.py`; MCP server at
`src/omnicursor/mcp/omnimarket_bridge_server.py`).

- Set `OMNIMARKET_ROOT` to a local omnimarket checkout; if unset, falls back to
  `omnimarket-main/` in the repo root (dev convenience only). **Never cloned at runtime.**
- Invocation: `python -m omnimarket.nodes.<node>` via subprocess, with
  `{OMNIMARKET_ROOT}/src` prepended to `PYTHONPATH`. Interpreter override:
  `OMNIMARKET_PYTHON`.
- Env: `OMNICURSOR_PATTERN_SYNC_HTTP` (optional pattern pull, **default off**),
  `OMNICURSOR_EMIT_SOCKET` (event socket, default `~/.omnicursor/emit.sock`).
- `compose.yaml` is local infra (Postgres/Redpanda/Valkey/intelligence) — **not** the
  primary bridge path; prefer subprocess invocation. Pattern writes stay local.

## Source-of-truth hierarchy

When documents disagree: **1.** actual codebase behavior → **2.** `CLAUDE.md` (this
file) → **3.** `docs/` (`ARCHITECTURE.md`, `CURRENT_STATE.md`) → **4.**
`omnicursor-team-guidance.md` (local; gitignored) → **5.** `omniclaude/` read-only
reference checkout (local-only; absent from a clean clone).

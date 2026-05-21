# OmniCursor — Current State

This document describes what the repo contains, what works, and what is in progress as of May 2026.

---

## What OmniCursor is

OmniCursor is a Cursor-native layer (rules, hooks, and a Python library) that brings OmniNode-style intelligence to Cursor sessions. It does three things:

1. **Routes every prompt** to the best-fit agent using a multi-strategy scoring engine
2. **Injects learned patterns** into each prompt's system message so the model benefits from past session outcomes
3. **Emits structured events** to the OmniNode event bus so session data feeds back into the intelligence pipeline

It is built entirely on Cursor's hook system — four Python scripts that fire at lifecycle events. The hooks use stdlib only (no pip dependencies) so they are fast and portable.

---

## Repo structure

```
OmniCursor/
├── .cursor/
│   ├── hooks.json          — registers the 4 hook entry points
│   ├── hooks/scripts/      — the 4 hook scripts
│   ├── hooks/lib/          — shared hook libraries
│   ├── agents/             — 17 agent JSON configs
│   ├── rules/              — 14 Cursor rules (.mdc)
│   └── skills/             — 17 skill directories (mirrored from skills/)
├── skills/                 — 17 skill markdown definitions (plus skills/README.md)
├── src/omnicursor/         — Python library (tests, CI, automation)
├── tests/                  — 28 `test_*.py` modules, `conftest.py`, 714 tests
├── eval/                   — routing evaluation scripts + labeled data
├── docs/                   — documentation
├── compose.yaml            — local Docker stack (Redpanda, Postgres, intelligence services)
└── scripts/                — utility scripts
```

---

## The 4 hooks

| Hook | Fires when | What it does |
|---|---|---|
| `scripts/user-prompt-submit.py` | User submits a prompt | Classifies prompt → selects agent → injects patterns + agent persona into system message |
| `scripts/shell-guard.py` | Before a shell command runs | Blocks 9 dangerous patterns, warns on 11 risky ones |
| `scripts/post-edit.py` | After a file is edited | Runs `ruff check` and `tsc --noEmit` diagnostically (never modifies files) |
| `scripts/stop.py` | Session ends | Classifies outcome (success/failed/abandoned/unknown), writes outbox record, emits events to sidecar socket |

---

## Agent routing

Every prompt is scored against **17 agents**. For each agent, `score_agent` in `src/omnicursor/scoring.py` (re-exported by `.cursor/hooks/lib/agent_scoring.py`) combines these strategies; the best score wins:

1. **Exact substring** on `explicit_triggers` → **0.95**
2. **Exact substring** on `context_triggers` → **0.80** (only if no stronger match)
3. **Fuzzy match** via `SequenceMatcher` on explicit triggers vs. prompt tokens — length-aware minimum similarity (**0.85** / **0.78** / **0.72** for short / medium / long triggers); the score is the winning ratio
4. **Keyword overlap** on `activation_keywords` → scaled **0.55–0.85** (at least two overlapping keywords)

`HARD_FLOOR = 0.55` — only agents scoring **≥ 0.55** can win selection; if none do, routing falls back to `polymorphic-agent`. For deeper detail, see `docs/dev/ROUTING_DEDUPLICATION.md`.

---

## The 17 skills

Skills are Markdown files under `skills/<slug>.md`, mirrored at `.cursor/skills/onex-<slug>/SKILL.md`. Canonical ids are **`onex-<slug>`** (YAML frontmatter `name` and slash picker). Activate via keywords in chat or `/onex-<slug>` in Cursor.

| Skill id | What it does |
|---|---|
| `onex-systematic-debugging` | Structured root-cause debugging |
| `onex-brainstorming` | Structured ideation |
| `onex-docs-reality-sync` | Align documentation with current behavior |
| `onex-writing-plans` | Write implementation plans |
| `onex-plan-ticket` | Generate YAML contract + create Linear ticket |
| `onex-plan-to-tickets` | Batch ticket creation from a plan file |
| `onex-execute-plan` | Full pipeline: plan review → tickets → implement → PR |
| `onex-pr-review` | Structured pull request review |
| `onex-pr-polish` | Final PR cleanup before merge |
| `onex-hostile-reviewer` | Multi-model adversarial review (v4.0, with gate mode) |
| `onex-defense-in-depth` | Security review methodology |
| `onex-merge-planner` | Plan a complex merge |
| `onex-insights-to-plan` | Convert observations into an implementation plan |
| `onex-handoff` | Structure a session handoff |
| `onex-using-git-worktrees` | Worktree-based parallel development |
| `onex-recap` | Summarise the current session |
| `onex-plan-review` | Adversarially review a plan before execution |

---

## Pattern learning (Option A)

When a session ends successfully and patterns were injected, `stop.py` writes back to `~/.omnicursor/learned_patterns.json` — updating injection counts and utilization scores. Patterns that perform well get higher weights; patterns that decay below threshold are evicted.

On the next session, `user-prompt-submit.py` loads these patterns and injects the most relevant ones (filtered by domain and keyword overlap) into the prompt's system message.

**What works:** full local learning loop — inject → outcome → write-back → re-inject next session.

---

## Pattern sync (Option B)

`lib/pattern_sync.py` in the hooks calls `GET /api/v1/patterns` on the omniintelligence HTTP API at session start to pull remotely-learned patterns. Local patterns always take priority — remote patterns are appended only if not already present locally (merge-local-priority).

`user-prompt-submit.py` also calls the API at every prompt submission (900ms timeout, falls back to local cache if unavailable).

**What works:** HTTP read sync runs when `OMNICURSOR_PATTERN_SYNC_HTTP=1` is set. Per-prompt API injection runs automatically if `INTELLIGENCE_SERVICE_URL` resolves (default `localhost:8053`).

---

## Event pipeline (Option C)

Option C adds a sidecar daemon that connects OmniCursor to the OmniNode event bus.

### How it works

```
Cursor session ends
  └─► stop.py
        ├─► ~/.omnicursor/outbox.jsonl    (durable record)
        └─► ~/.omnicursor/emit.sock       (live signal)
              └─► sidecar drain_loop (2s tick)
                    └─► Kafka/Redpanda → omniintelligence
```

### Components

| Component | File | Status |
|---|---|---|
| Outbox writer | `src/omnicursor/session_outbox.py` | Working |
| Socket listener | `src/omnicursor/sidecar/socket_listener.py` | Working |
| Drain loop | `src/omnicursor/drainer/loop.py` | Working |
| Kafka publisher | `src/omnicursor/drainer/kafka_publisher.py` | Working (requires confluent-kafka + Redpanda) |
| Noop publisher | `src/omnicursor/drainer/publisher.py` | Working (for testing) |
| Daemon CLI | `src/omnicursor/sidecar/daemon.py` | Working |
| Launcher | `scripts/run_sidecar.sh` | Working |
| Outbox watcher | `scripts/watch_outbox.py` | Working (colorized terminal monitor) |
| Smoke test | `scripts/smoke_test.py` | Working |

### Running the sidecar

```bash
bash scripts/run_sidecar.sh --publisher noop     # testing
bash scripts/run_sidecar.sh --publisher kafka    # production (needs Redpanda)
```

**What works:** full socket → outbox → drain → publish pipeline. Tested end-to-end with Cursor sessions. Kafka publisher works when Redpanda is running via `docker compose up redpanda -d`.

---

## Infrastructure (Docker Compose)

`compose.yaml` defines the full local OmniNode stack:

| Service | Port | What it is |
|---|---|---|
| `postgres` | 5436 | Database for intelligence services |
| `redpanda` | 19092 | Kafka-compatible message broker |
| `valkey` | 16379 | Redis-compatible cache |
| `intelligence-reducer` | 18091 | omniintelligence reducer (pattern storage + scoring) |
| `intelligence-orchestrator` | 18092 | omniintelligence orchestrator |
| `quality-scoring-compute` | 18093 | Quality scoring node |

Start the full stack: `docker compose up -d`  
Start just Redpanda: `docker compose up redpanda -d`

---

## MCP integrations

| Server | Config location | What it does |
|---|---|---|
| `linear` | `~/.cursor/mcp.json` | Linear ticket operations (`tracker.*` tools) |
| `omnicursor-omnimarket` | `.cursor/mcp.json` (gitignored, set locally) | Omnimarket node bridge |

`.cursor/mcp.json` is gitignored — each developer sets their own local paths.

---

## Test suite

```bash
source .venv/bin/activate
pytest tests/ -q          # 714 tests (pytest --collect-only)
ruff check src/ tests/ .cursor/hooks/   # lint
```

**714** tests collect under `tests/`; the full suite passes in CI and via `.githooks/pre-commit` on a healthy `main` checkout (verify locally with `pytest tests/ -q`).

---

## Branches

| Branch | What it contains |
|---|---|
| `main` | Default branch — hooks, routing, pattern learning (Option A), pattern sync (Option B), and Option C (sidecar, outbox, drainer, Kafka publisher, event registry, demo scripts) |
| `intelligence/option-b` | Topic branch for Option B–era work; compare to `main` with `git diff` / `git log` if you rely on it |
| `intelligence/option-c` | Topic branch for Option C integration; may match or diverge from `main` — compare before assuming parity |

Other remotes (for example `feature/omnimarket-mcp-bridge`) exist for in-flight work and are not listed here.

---

## Option C and `main`

The Option C stack (sidecar daemon, socket drain, Kafka/Redpanda path, outbox, and smoke tooling) **lives on `main`**: `src/omnicursor/drainer/`, `src/omnicursor/sidecar/`, `src/omnicursor/session_outbox.py`, `scripts/run_sidecar.sh`, `scripts/smoke_test.py`, `scripts/watch_outbox.py`, `config/event_registry/omnicursor.yaml`, and per-prompt integrations in `user-prompt-submit.py` where applicable. **`tests/test_sidecar.py`** collects **13** sidecar-focused tests.

Use branch **`intelligence/option-c`** only when you need history or a parallel line of work — it is not required to obtain Option C sources; **`main` already contains them**.

# OmniCursor — Project Handoff

**Audience:** A developer picking up this repo after another session or teammate.  
**As of:** May 2026.  
**Supersedes:** Use this file for **active onboarding**. Older session handoffs live in [`archive/dev/handoffs/`](./archive/dev/handoffs/README.md) and are historical only.

---

## Read this first (30-minute path)

Read in this order. Stop when you have enough context for your task; come back for depth.

| Order | Document | Why |
|-------|----------|-----|
| 1 | [`README.md`](../README.md) | One-page product shape, layout, hooks table, test commands |
| 2 | [`CLAUDE.md`](../CLAUDE.md) | **Primary contributor reference** — commands, architecture, conventions, omnimarket bridge, constraints |
| 3 | [`CURRENT_STATE.md`](./CURRENT_STATE.md) | What actually works today (Options A/B/C, branches, MCP, Docker, test counts) |
| 4 | [`QUICKSTART.md`](./QUICKSTART.md) | Install as a Cursor plugin, hooks/skills behavior, Linear MCP setup |
| 5 | This file | Onboarding map, pitfalls, and “where to look” for common work |

**Then, by task:**

| Task | Next read |
|------|-----------|
| Capstone / sponsor alignment | [`SOW_vs_current_architecture.md`](./SOW_vs_current_architecture.md) |
| 3-bucket model / starter-pack rules | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| Implementation decisions | [`dev/OMNICURSOR_IMPLEMENTATION_BRIEF.md`](./dev/OMNICURSOR_IMPLEMENTATION_BRIEF.md) |
| Hook vs library ownership | [`dev/ADR-hook-first-architecture.md`](./dev/ADR-hook-first-architecture.md) |
| Agent scoring (hooks + `agents.py`) | [`dev/ROUTING_DEDUPLICATION.md`](./dev/ROUTING_DEDUPLICATION.md) |
| Intelligence pipeline (A/B/C) | [`dev/INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md`](./dev/INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md) |
| OmniMarket / node bridge | [`CLAUDE.md`](../CLAUDE.md) § Omnimarket bridge + MCP `omnicursor-omnimarket` |
| Demo / presentation | [`demo/README.md`](./demo/README.md) |
| Full doc map | [`README.md`](./README.md) |

**Do not start with** [`archive/`](./archive/README.md) unless you need migration history or a dated session note.

---

## What this repo is (one paragraph)

**OmniCursor** is a **Cursor-native** layer: **rules** (`.cursor/rules/`), **hooks** (four stdlib-only lifecycle scripts), and **17 file-backed skills** (`skills/*.md`, mirrored under `.cursor/skills/onex-*/`). A **Python library** (`src/omnicursor/`) mirrors routing, skills, compliance smoke-checks, and node contracts for **pytest and CI** — hooks do not import it at runtime.

It routes prompts to agents, guards shell commands, runs diagnostic lint on edits, classifies session outcomes, and optionally syncs patterns and events to the wider OmniNode stack. **OmniMarket** owns node/workflow semantics; OmniCursor stays a **thin** intent → tool/subprocess mapper.

---

## Mental model: four layers

```
User in Cursor
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ Rules (.cursor/rules/*.mdc)  — methodology, buckets     │
│ Skills (skills/*.md)         — multi-step workflows     │
│ Agents (.cursor/agents/*.json) — routing personas       │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ Hooks (.cursor/hooks/scripts/*.py) — deterministic only │
│   prompt submit │ shell guard │ post-edit │ stop        │
└─────────────────────────────────────────────────────────┘
    │
    ├──► ~/.omnicursor/  (patterns, events, sessions, outbox)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ src/omnicursor/  — tests, CI, sidecar, drainer, bridge  │
└─────────────────────────────────────────────────────────┘
    │
    ▼ (optional)
Linear MCP │ OmniMarket nodes │ Kafka/Redpanda │ compose stack
```

---

## Repository map (high signal)

| Path | What it is |
|------|------------|
| `.cursor/rules/` | 14 `.mdc` rules; `00`–`03` always-on; `10`–`19` keyword-activated |
| `.cursor/hooks.json` + `.cursor/hooks/scripts/` | Four hook entrypoints (see [`CURRENT_STATE.md`](./CURRENT_STATE.md)) |
| `.cursor/agents/` | 17 JSON agent configs (activation patterns) |
| `.cursor/skills/onex-*/SKILL.md` | Mirrored skills for Cursor `/` picker |
| `skills/` | Canonical skill Markdown (CI scans here) |
| `src/omnicursor/` | `agents`, `scoring`, `skills`, `compliance`, `nodes/*/contract.yaml`, sidecar/drainer |
| `tests/` | Full pytest suite (~714 tests on healthy `main`) |
| `eval/` | Routing evaluation scripts + labeled data |
| `docs/` | Active documentation (this handoff, architecture, dev refs) |
| `docs/plans/` | **In-progress** implementation plans only |
| `docs/archive/` | Completed plans, old handoffs, capstone artifacts — **not** day-to-day |
| `compose.yaml` | Local Postgres, Redpanda, Valkey, intelligence services |
| `omniclaude-main/` | **Read-only** reference — never modify |
| `omnimarket-main/` or `OMNIMARKET_ROOT` | Local OmniMarket checkout for node bridge (not cloned at runtime) |

---

## First-time setup checklist

```bash
cd /path/to/OmniCursor
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

**Cursor plugin (applies to all workspaces):**

```bash
./scripts/install-plugin.sh
# Reload Cursor (Developer: Reload Window)
```

**Verify:**

```bash
pytest tests/ -q
ruff check src/ tests/ .cursor/hooks/
./scripts/install-plugin.sh --status
```

**Optional local intelligence stack:**

```bash
docker compose up -d          # full stack
docker compose up redpanda -d # Kafka only (Option C)
bash scripts/run_sidecar.sh --publisher noop   # test event drain
```

---

## Hooks (what runs automatically)

Configured in [`.cursor/hooks.json`](../.cursor/hooks.json). **Stdlib only** — no pip deps in hook processes.

| Hook | Script | Blocks? | Role |
|------|--------|---------|------|
| `beforeSubmitPrompt` | `user-prompt-submit.py` | No | Agent scoring, pattern injection (`systemMessage`) |
| `beforeShellExecution` | `shell-guard.py` | **Yes** (9 hard blocks) | Dangerous commands; DoD guard for Linear “done” |
| `afterFileEdit` | `post-edit.py` | No | Diagnostic `ruff` / `tsc` — never `--fix` |
| `stop` | `stop.py` | No | Session outcome (4-gate), outbox, optional sidecar socket |

Only **shell-guard** can return `{"permission": "deny"}`. Other hook stdout is informational; events also append to `~/.omnicursor/events.jsonl`.

---

## Agent routing

- **17 agents** in `.cursor/agents/*.json` merged with hardcoded contexts in `src/omnicursor/agents.py`.
- Shared scoring: `src/omnicursor/scoring.py` (used by hooks via `agent_scoring.py`).
- Strategies: exact triggers → fuzzy → keyword overlap; **`HARD_FLOOR = 0.55`**; fallback **`polymorphic-agent`**.
- Eval data: `eval/`.

---

## Skills (17) and buckets

Canonical ids: **`onex-<slug>`** (YAML `name`, `/` picker, compliance registry keys).

| Bucket | Rule | Examples |
|--------|------|----------|
| **1** | Pure methodology; no external reads | `onex-brainstorming`, `onex-writing-plans`, `onex-pr-review`, … |
| **2** | Bounded local files only | `onex-plan-ticket` |
| **3** | External services (Linear MCP, Kafka, validators) | `onex-plan-to-tickets`, `onex-execute-plan` |

**Adding a skill:** create `skills/<slug>.md`, mirror to `.cursor/skills/onex-<slug>/SKILL.md`, add `compliance.py` entry, update `tests/test_compliance.py` and `tests/test_skills.py`.

**Cursor rules cannot fake Bucket 3 success** — if Linear/Kafka is down, document manual steps or dry-run only.

---

## Intelligence options (A / B / C)

Summarized in [`CURRENT_STATE.md`](./CURRENT_STATE.md); detail in [`dev/INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md`](./dev/INTELLIGENCE_LAYER_CURRENT_STATE_AND_OPTIONS.md).

| Option | What | Env / infra |
|--------|------|-------------|
| **A** | Local pattern learn/write at `~/.omnicursor/learned_patterns.json` | Works offline |
| **B** | HTTP pull from omniintelligence (`pattern_sync`) | `OMNICURSOR_PATTERN_SYNC_HTTP=1`, `INTELLIGENCE_SERVICE_URL` |
| **C** | Session events → outbox → sidecar → Kafka | `scripts/run_sidecar.sh`, Redpanda, `confluent-kafka` |

**Option C is on `main`** — do not assume you must check out `intelligence/option-c` for sidecar sources.

---

## OmniMarket bridge (OmniNode execution)

- Set **`OMNIMARKET_ROOT`** to a local omnimarket checkout (or dev fallback `omnimarket-main/` in repo root).
- **Preferred invocation:** `python -m omnimarket.nodes.<node_name>` subprocess with `{OMNIMARKET_ROOT}/src` on `PYTHONPATH`.
- **Out of scope for OmniCursor:** duplicating node business logic in rules/hooks; `onex run <contract.yaml>`; direct omniintelligence HTTP as primary bridge.
- MCP server **`omnicursor-omnimarket`** — configure in local `.cursor/mcp.json` (gitignored).

Ownership: see `.cursor/rules/03-omnicursor-ownership.mdc` and [`SOW_vs_current_architecture.md`](./SOW_vs_current_architecture.md).

---

## MCP and external config

| Integration | Where configured | Used for |
|-------------|------------------|----------|
| Linear | `~/.cursor/mcp.json` | Bucket 3 ticketing (`tracker.*`) |
| OmniMarket | `.cursor/mcp.json` (local, gitignored) | Node bridge tools |

---

## Local state (`~/.omnicursor/`)

| File / path | Purpose |
|-------------|---------|
| `learned_patterns.json` | Option A pattern store |
| `events.jsonl` | Hook event log |
| `sessions/<conversation_id>.json` | Session facts (ticket IDs, `ci_passing`, routing) |
| `sessions/.../dispatch_claim` | Shell dispatch guard (see rule `00`) |
| `outbox.jsonl` | Option C durable events |
| `emit.sock` | Sidecar live signal |

Before context compaction, re-read session JSON or `@file` plans under `docs/plans/` — do not rely on chat memory alone.

---

## Testing and CI

- **Pre-commit:** `.githooks/pre-commit` — `ruff`, full `pytest`, skill compliance coverage.
- **Emergency bypass only:** `git commit --no-verify` (user must request explicitly).
- **CI:** GitHub Actions on PRs to `main`.
- Hooks: **never** add pip dependencies to hook scripts.

---

## Hard constraints (avoid rework)

1. **Never modify** `omniclaude-main/`.
2. **Never commit secrets** — see `.cursor/rules/02-no-secrets-in-commits.mdc`.
3. **Hooks:** stdlib only; `post-edit.py` never auto-fixes files.
4. **Do not duplicate OmniMarket node logic** in Cursor rules or hooks.
5. **`.cursor/rules/*.mdc`** are teaching/rubric artifacts — edit deliberately.
6. **Research rule `01-codebase-research.mdc`** may apply in graded sessions (bounded reads + announcement line).
7. **Source-of-truth when docs disagree:** codebase behavior → `CLAUDE.md` → `dev/OMNICURSOR_IMPLEMENTATION_BRIEF.md` → team guidance (gitignored) → `omniclaude-main/` reference.

---

## Common continuation tasks

| Goal | Where to work |
|------|----------------|
| Fix routing / agent selection | `.cursor/agents/`, `src/omnicursor/scoring.py`, `eval/` |
| Change hook behavior | `.cursor/hooks/scripts/`, matching tests under `tests/` |
| Add or update a skill | `skills/`, `.cursor/skills/`, `compliance.py`, rules `10`–`19` |
| Node contract / ONEX shape | `src/omnicursor/nodes/*/contract.yaml`, `docs/dev/OMNICURSOR_NODE_CONTRACTS.md` |
| Bridge / omnimarket | `src/omnicursor/` bridge modules, MCP descriptors, `OMNIMARKET_ROOT` |
| Intelligence / Kafka | `src/omnicursor/sidecar/`, `drainer/`, `compose.yaml`, `scripts/run_sidecar.sh` |
| Write an implementation plan | `docs/plans/` (move to `docs/archive/plans/` when done) |
| Session handoff for next chat | Skill `onex-handoff` or rule `15-handoff.mdc`; optional dated file under `docs/archive/dev/handoffs/` |

---

## Branches (May 2026)

| Branch | Notes |
|--------|-------|
| `main` | Default — hooks, routing, Options A+B+C, sidecar, tests |
| `intelligence/option-b`, `intelligence/option-c` | Topic/history branches — **diff against `main`** before assuming divergence |
| Feature branches | e.g. omnimarket MCP bridge — check `git branch -a` |

---

## Archive vs active docs

| Location | Use |
|----------|-----|
| `docs/` (except `archive/`) | Living reference |
| `docs/plans/` | Active plans only |
| `docs/archive/` | Completed handoffs, migration roadmaps, capstone PDFs — safe to ignore for daily dev |

Notable archived handoffs: `docs/archive/dev/HANDOFF.md`, `MIGRATION_PHASES_HANDOFF.md`, `docs/archive/dev/handoffs/2026-05-10-option-a-handoff.md`.

---

## Generating a narrower handoff

For **end-of-session** context (not full repo onboarding), use the **`onex-handoff`** skill ([`skills/handoff.md`](../skills/handoff.md)) or ask in chat with “session handoff.” That produces task-specific remaining work; this document stays the **project-level** pickup guide.

---

## Quick command reference

```bash
# Dev loop
source .venv/bin/activate
pytest tests/ -v
pytest tests/test_agents.py -v
pytest tests/ -k "sidecar"
ruff check src/ tests/ .cursor/hooks/

# Plugin
./scripts/install-plugin.sh --status

# Sidecar (Option C)
bash scripts/run_sidecar.sh --publisher noop
python scripts/watch_outbox.py   # if present in checkout

# Docker
docker compose up -d
```

---

## Document maintenance

When major behavior changes (new hook, skill count, Option status, test count), update **`CURRENT_STATE.md`** and the relevant sections of **this file** and **`docs/README.md`**.

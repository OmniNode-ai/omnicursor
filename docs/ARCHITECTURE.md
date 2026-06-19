# OmniCursor Architecture

OmniCursor is a **Cursor plugin** that ports the OmniClaude methodology to Cursor: **rules**, **hooks**, **skills**, and **agent routing** — with a Python library for tests and CI. It runs locally by default; integration with the wider OmniNode stack (OmniIntelligence, OmniMarket, Kafka) is optional.

---

## Design goals

| Goal | How |
|------|-----|
| **Deterministic hooks** | Four lifecycle scripts — stdlib only, always exit 0, never block the UI |
| **Thin Cursor layer** | Rules and skills teach behavior; OmniMarket owns workflow/node logic |
| **Testable routing** | Shared scoring engine in hooks and `src/omnicursor/scoring.py` |
| **Progressive integration** | Works offline (Option A); optional HTTP patterns (B) and event bus (C) |

---

## System overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Cursor IDE (any workspace)                  │
├─────────────────────────────────────────────────────────────────────┤
│  Rules (.cursor/rules/*.mdc)     — always-on + keyword methodology│
│  Skills (.cursor/skills/onex-*/SKILL.md) — multi-step workflows     │
│  Agents (.cursor/agents/*.json)  — routing personas                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ user prompts, shell, edits, stop
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Hooks (.cursor/hooks/scripts/*.py) — stdlib-only, non-blocking     │
│    beforeSubmitPrompt │ beforeShellExecution │ afterFileEdit │ stop │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
   ~/.omnicursor/         src/omnicursor/      Optional stack
   (local state)          (tests, sidecar,      (compose.yaml:
                          drainer, bridge)       Redpanda, omniintelligence)
```

**Runtime split:** Hooks do **not** import `src/omnicursor/` at runtime. The Python package mirrors hook logic for pytest, hosts the sidecar/drainer, and exposes the OmniMarket bridge for Bucket 3 skills.

---

## The four surfaces

### 1. Cursor rules (`.cursor/rules/`)

14 `.mdc` files define the **behavior surface** for the model.

| Always on | Keyword-activated |
|-----------|-------------------|
| `00-omninode-concepts` — ONEX vocabulary, 3-bucket model, pipeline stages | `10` brainstorming · `11` writing-plans · `12` plan-ticket |
| `01-codebase-research` — bounded file-reading policy | `13` systematic-debugging · `14` pr-review · `15` handoff |
| `02-no-secrets-in-commits` | `16` plan-to-tickets · `17` plan-review · `18` recap · `19` execute-plan |
| `03-omnicursor-ownership` — OmniCursor vs OmniMarket boundary | |

See [`.cursor/rules/README.md`](../.cursor/rules/README.md).

### 2. Cursor hooks (`.cursor/hooks/`)

Configured in [`.cursor/hooks.json`](../.cursor/hooks.json). Each hook is a thin Python entrypoint under `scripts/` with shared helpers in `lib/`, `_common.py`, and `pattern_loader.py`.

| Hook | Script | Blocks UI? | Role |
|------|--------|------------|------|
| `beforeSubmitPrompt` | `user-prompt-submit.py` | No | Agent scoring, pattern injection via `systemMessage`, session init |
| `beforeShellExecution` | `shell-guard.py` | **Yes** (hard blocks) | Dangerous-command guard, DoD enforcement |
| `afterFileEdit` | `post-edit.py` | No | Diagnostic `ruff` / `tsc` — never auto-fix |
| `stop` | `stop.py` | No | Session outcome (4-gate), recap, outbox write |

**Constraints (non-negotiable):**

- Stdlib only in hook processes — no pip dependencies
- Always exit 0; failures are logged, not propagated to Cursor
- Only `shell-guard` may return `{"permission": "deny"}`
- Heavy work (Kafka, node execution) stays out of hooks

### 3. Skills (17)

Canonical Markdown lives under [`skills/`](../skills/); Cursor discovers mirrored copies at [`.cursor/skills/onex-<slug>/SKILL.md`](../.cursor/skills/).

Each skill has:

- YAML frontmatter with `name: onex-<slug>` (shown in the `/` picker)
- A compliance registry entry in `src/omnicursor/compliance.py`
- A keyword-activated rule in `.cursor/rules/10`–`19` (where applicable)

### 4. Python library (`src/omnicursor/`)

Used by **pytest**, **CI**, and optional local tooling — not by hooks at runtime.

| Module | Role |
|--------|------|
| `scoring.py` | Canonical `score_agent` engine (`HARD_FLOOR = 0.55`) |
| `agents.py` | Category → routing context; merges with `.cursor/agents/*.json` |
| `skills.py` | Load skill Markdown into `SkillDocument` |
| `compliance.py` | Keyword rubric checks for skill adherence |
| `session_outbox.py` | Durable outbox writer (`omnicursor.session_outcome.v1`) |
| `sidecar/` + `drainer/` | Option C: socket listener → outbox → Kafka/OmniDash |
| `sync/pattern_sync.py` | Option B: HTTP pull from omniintelligence |
| `omnimarket_bridge.py` | Subprocess bridge to local OmniMarket nodes |
| `nodes/*/contract.yaml` | ONEX-shaped contracts binding hooks to node semantics |

See [`src/omnicursor/README.md`](../src/omnicursor/README.md).

---

## 3-bucket skill model

Skills are classified by how much external infrastructure they need. Rule `00-omninode-concepts` is the source of truth.

| Bucket | Rule | Examples |
|--------|------|----------|
| **1 — Pure methodology** | No external service; may write local files | `onex-brainstorming`, `onex-writing-plans`, `onex-pr-review`, `onex-systematic-debugging` |
| **2 — Local-data hybrid** | Reads bounded local files / cwd context | `onex-plan-ticket` |
| **3 — External integration** | Requires Linear MCP, Kafka, or OmniMarket nodes | `onex-plan-to-tickets`, `onex-execute-plan` |

**Cursor rules cannot fake Bucket 3 success.** If Linear or Kafka is unreachable, skills must document manual steps or dry-run output — not simulate API calls.

---

## 5-stage pipeline

```
1. BRAINSTORM  → design doc          (Bucket 1 — onex-brainstorming)
2. PLAN        → implementation plan (Bucket 1 — onex-writing-plans)
3. TICKET      → YAML ticket template (Bucket 2 — onex-plan-ticket)
4. DECOMPOSE   → Linear child tickets (Bucket 3 — onex-plan-to-tickets)
5. EXECUTE     → agent-driven implementation (Bucket 3 — onex-execute-plan)
```

Stages 1–3 work offline. Stages 4–5 need Linear MCP and/or OmniMarket.

---

## Agent routing

17 JSON configs in [`.cursor/agents/`](../.cursor/agents/) define activation patterns. On every prompt, `user-prompt-submit.py` runs multi-strategy scoring:

1. Exact trigger match
2. Fuzzy match
3. Keyword overlap

If the best score is below **`HARD_FLOOR` (0.55)**, routing falls back to **`polymorphic-agent`**.

Output is injected as a `systemMessage` JSON block: agent persona, recommended skill, learned patterns, delegation rule, and a once-per-session handoff nudge.

The same scoring logic lives in `src/omnicursor/scoring.py` for tests and eval scripts under `eval/`.

---

## Local state (`~/.omnicursor/`)

| Path | Purpose |
|------|---------|
| `learned_patterns.json` | Option A — pattern learning cache |
| `events.jsonl` | Structured hook event log |
| `sessions/<conversation_id>.json` | Session facts (routing, ticket IDs, CI status) |
| `sessions/.../dispatch_claim` | Shell dispatch guard (see rule `00`) |
| `last-recap.md` | Previous session recap (injected at next session start) |
| `outbox.jsonl` | Option C — durable session outcomes for drainer |
| `emit.sock` | Unix socket for live hook → sidecar events |

**Privacy:** `learned_patterns.json` may contain up to 60 characters of prompt text in descriptions. Data stays local unless Option B HTTP sync or Option C Kafka publishing is enabled.

---

## Intelligence options (A / B / C)

OmniCursor layers optional intelligence on top of local hook behavior.

| Option | What | Requires |
|--------|------|----------|
| **A — Local patterns** | Learn/write patterns at `~/.omnicursor/learned_patterns.json` | Nothing — works offline |
| **B — HTTP sync** | Pull merged patterns from omniintelligence on each prompt | `OMNICURSOR_PATTERN_SYNC_HTTP=1`, `INTELLIGENCE_SERVICE_URL`, compose stack |
| **C — Event bus** | Session events → outbox → sidecar → Kafka/OmniDash | `scripts/run_sidecar.sh`, Redpanda, `confluent-kafka` |

```
Option A (default)     Hook → learned_patterns.json
Option B               Hook → HTTP GET /api/v1/patterns → merge with local cache
Option C               Hook → emit.sock / outbox.jsonl → sidecar → Kafka topics
```

Sidecar entry point: `python -m omnicursor.sidecar.daemon [--publisher kafka|omnidash|noop]`.

Environment template: [`.env.omninode.example`](../.env.omninode.example).

---

## Node contracts

Five Cursor-native node contracts under `src/omnicursor/nodes/` describe the ONEX shape of each hook lifecycle event. They are **documentation and test anchors** — the live implementation is always the stdlib hook script referenced in each contract's `cursor_native` block.

| Contract | Hook event |
|----------|------------|
| `node_cursor_prompt_orchestrator` | `beforeSubmitPrompt` |
| `node_cursor_shell_guard_effect` | `beforeShellExecution` |
| `node_cursor_file_edit_effect` | `afterFileEdit` |
| `node_cursor_session_outcome_orchestrator` | `stop` |
| `node_cursor_pattern_injection_compute` | pattern injection (subset of prompt hook) |

Each contract declares input/output schemas, `cursor_native.implementation`, and a local `events.jsonl` bus — not Kafka topic strings in app code.

---

## OmniCursor vs OmniMarket ownership

```
OmniCursor                          OmniMarket
──────────                          ──────────
Collect user intent                 Workflow + business logic
Route prompts to agents             Node handlers + contracts
Guard shell / lint edits            Tool-provider semantics
Invoke MCP / subprocess bridge  →   Execute nodes (local-review, etc.)
Render results to user              Emit/consume Kafka events
```

OmniCursor **must not** duplicate OmniMarket node logic in rules or hooks. Bucket 3 skills invoke nodes via:

```bash
PYTHONPATH="${OMNIMARKET_ROOT}/src" python -m omnimarket.nodes.<node_name>
```

Set `OMNIMARKET_ROOT` to a local omnimarket checkout (see `.env.omninode.example`).

---

## Plugin packaging

OmniCursor installs as a **user-level Cursor plugin** via symlink:

```
~/.cursor/plugins/local/omnicursor → /path/to/OmniCursor
```

Manifest: [`.cursor-plugin/plugin.json`](../.cursor-plugin/plugin.json) declares `rules`, `agents`, `skills`, and `hooks` paths. One install applies to **every workspace** — no per-repo setup.

---

## Testing and CI

```
pytest tests/          — routing, hooks, skills, compliance, sidecar, drainer
ruff check             — src/, tests/, .cursor/hooks/
.githooks/pre-commit   — same checks locally before commit
GitHub Actions         — PRs to main
```

Hooks are tested by importing hook modules with mocked I/O; the Python library is tested independently.

---

## Roadmap: shared emit daemon

OmniCursor currently ships a **bespoke sidecar + drainer** for Option C. The target architecture (see repo-root `OMNICURSOR_DISPATCHER_PLAN.md`) is to **reuse omnimarket's shared `node_emit_daemon`** — the same stdlib `EmitClient` OmniClaude uses — and delete the duplicate emission stack. Hooks already include a vendored `emit_client.py` compatible with that wire protocol.

Until that migration lands, treat Option C as **local/demo infrastructure**; production bus emission will converge on the shared daemon.

---

## Related docs

| Doc | Topic |
|-----|-------|
| [QUICKSTART.md](./QUICKSTART.md) | Install, hooks, skills, Linear MCP |
| [HANDOFF.md](./HANDOFF.md) | Developer onboarding path |
| [README.md](./README.md) | Documentation map |
| [`.cursor/rules/00-omninode-concepts.mdc`](../.cursor/rules/00-omninode-concepts.mdc) | Vocabulary and bucket table (always active) |

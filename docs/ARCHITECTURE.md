# Architecture

> **Status:** Living reference. Last verified against the codebase: **June 2026**.
> When this document and the code disagree, the **code wins** — see [Source-of-truth hierarchy](#source-of-truth-hierarchy).

OmniCursor is a **Cursor-native adaptation of OmniClaude**. It packages an
agent/methodology layer as a **Cursor plugin** and backs it with a Python
library that exists for **tests, CI, and optional scripting** — the IDE
behavior itself does not import that library at runtime.

This document explains how the pieces fit together. For *what currently works*
versus *what is opt-in or aspirational*, read [`CURRENT_STATE.md`](./CURRENT_STATE.md).

---

## 1. The big picture

```
                        Cursor IDE (user prompt, shell, file edits, stop)
                                          │
        ┌─────────────────────────────────┴─────────────────────────────────┐
        │                         BEHAVIOR SURFACE                            │
        │                                                                     │
        │  Rules (.cursor/rules/*.mdc)      → injected guidance / methodology │
        │  Skills (skills/*.md + mirror)    → multi-step playbooks the model  │
        │                                     reads from disk                 │
        │  Agents (.cursor/agents/*.json)   → routing personas                │
        │  Hooks (.cursor/hooks/scripts/)   → deterministic, stdlib-only      │
        │                                     lifecycle scripts               │
        └─────────────────────────────────┬─────────────────────────────────┘
                                          │ reads / writes
                                          ▼
                          ~/.omnicursor/  (events, sessions, patterns, outbox)
                                          │
                                          ▼ (optional, opt-in)
        ┌─────────────────────────────────────────────────────────────────┐
        │  src/omnicursor/  — tests, CI, scripting, OmniMarket bridge       │
        │                                                                   │
        │  Linear MCP │ OmniMarket nodes │ shared emit daemon │ compose     │
        └─────────────────────────────────────────────────────────────────┘
```

There are **four behavior surfaces** plus **one support library**:

| Surface | Location | Role |
|---------|----------|------|
| **Rules** | `.cursor/rules/*.mdc` (14 files) | Instructions injected into the model's context |
| **Skills** | `skills/*.md` (17) + `.cursor/skills/onex-*/SKILL.md` (17) | Methodology playbooks the model reads on demand |
| **Agents** | `.cursor/agents/*.json` (17) | Routing personas scored against the prompt |
| **Hooks** | `.cursor/hooks/scripts/*.py` (4) | Deterministic, stdlib-only lifecycle scripts |
| **Library** | `src/omnicursor/` | Routing, scoring, skills, compliance, contracts, bridge — for **pytest/CI/scripting only** |

> **Key boundary:** the hooks are **stdlib-only** and must run without a
> virtualenv. The active scripts reach the library logic by inserting `src/` (and
> `.cursor/hooks/lib/`) onto `sys.path` and importing `omnicursor.*` **directly** —
> the library is the single source of truth, the scripts are thin entrypoints.
> Self-contained *duplicated copies* of the logic exist only in the unwired legacy
> `.cursor/hooks/on_*.py`. See [§4 Hooks](#4-hooks) and [§7 Node contracts](#7-node-contracts-onex-shaped).

---

## 2. Rules

14 `.mdc` files in `.cursor/rules/`, each Markdown with YAML frontmatter.

- **Always-on (4):** `00-omninode-concepts`, `01-codebase-research`,
  `02-no-secrets-in-commits`, `03-omnicursor-ownership` — all carry
  `alwaysApply: true`.
- **Keyword/`@mention`-activated (10):** `10`–`19` drive methodology workflows
  (brainstorming, writing plans, plan-ticket, systematic debugging, PR review,
  handoff, plan-to-tickets, plan-review, recap, execute-plan). Each rule points
  the model at the matching `.cursor/skills/onex-<slug>/SKILL.md`.

Rules are **teaching/rubric artifacts** — change them deliberately.

---

## 3. Skills

17 methodology playbooks. Each skill exists in **two places**:

| Copy | Path | Who reads it |
|------|------|--------------|
| **Canonical** | `skills/<slug>.md` (bare slug) | **CI/parity** scans here |
| **Cursor mirror** | `.cursor/skills/onex-<slug>/SKILL.md` | The Cursor `/` picker **and** the Python `SkillRepository` load here |

> **The two copies are asymmetric.** `SkillRepository` (via
> `db.SKILLS_DIR = REPO_ROOT/.cursor/skills`) loads **only** the mirror, while CI
> scans `skills/`. Editing only `skills/<slug>.md` changes nothing at runtime
> until the mirror is updated — and `tests/test_skills.py::test_skills_dual_path_parity`
> enforces that the two are **content-identical** (UTF-8 text comparison).

**Canonical id:** `onex-<slug>` (e.g. `onex-systematic-debugging`). The bare
`<slug>` is the on-disk stem; the loader also accepts a legacy `onex:` colon form
for back-compat.

### 3-bucket classification

Buckets describe a skill's external-dependency level:

| Bucket | Meaning | Count | Skills |
|--------|---------|-------|--------|
| **1** | Pure methodology, no external calls | 14 | brainstorming, writing-plans, systematic-debugging, pr-review, pr-polish, hostile-reviewer, defense-in-depth, docs-reality-sync, merge-planner, insights-to-plan, handoff, using-git-worktrees, recap, plan-review |
| **2** | *(retired — formerly plan-ticket YAML-only mode)* | 0 | — |
| **3** | Linear MCP integration (`tracker.*` tools) | 3 | plan-ticket, plan-to-tickets, execute-plan |

> Buckets live only in prose (rule `00` / this doc) — there is **no machine-readable
> bucket field** in the skill frontmatter, so they can silently drift. A live
> example of the **rule-vs-skill** distinction: the **skill** `onex-plan-ticket`
> is treated as Bucket 3 (Linear MCP), but the **rule** `12-plan-ticket.mdc`
> still self-labels **Bucket 2** and emits a local YAML ticket-contract template
> with no external calls. "Bucket 2" is *retired at the skill level* but still
> used at the rule level.

### Plan-ticket repo detection

The `12-plan-ticket` rule picks the target OmniNode repo for a ticket with a
**deterministic 3-priority chain** — this is the canonical spec that
`tests/rubrics/plan-ticket.md` grades against. Valid repo names (exactly these 7):
`omniclaude`, `omnibase_core`, `omnibase_infra`, `omnidash`, `omniintelligence`,
`omnimemory`, `omninode_infra`.

1. **Priority 1 — CWD or prompt match.** If the working-directory path *or* the
   prompt text contains one of the 7 names (case-insensitive substring), use it. **Stop.**
2. **Priority 2 — README project name.** Otherwise, if `README.md` names one of the
   7 as its project (e.g. an `# omniclaude` heading), use it. **Stop.**
3. **Priority 3 — Ask.** Otherwise, ask exactly **one** multiple-choice question
   (options A–G for the 7 repos + H "Other") and wait for the answer — **never guess.**

Research is bounded (rule `01`): the rule reads at most `README.md` plus one
directory listing, then emits the YAML ticket-contract template.

---

## 4. Hooks

Four Cursor lifecycle events are wired in `.cursor/hooks.json` to four
**stdlib-only** scripts:

| Event | Active script | Can block? | Role |
|-------|---------------|------------|------|
| `beforeSubmitPrompt` | `scripts/user-prompt-submit.py` | No | Classifies the prompt → best agent; selects/injects learned patterns; emits a `systemMessage` |
| `beforeShellExecution` | `scripts/shell-guard.py` | **Yes** | Two-tier guard: **9 HARD_BLOCK** (deny) + **12 SOFT_WARN** (allow + warning); optional DoD/dispatch gates |
| `afterFileEdit` | `scripts/post-edit.py` | No | Diagnostic `ruff check` (`.py`) and `tsc --noEmit` (`.ts`) — **never `--fix`**, never modifies files |
| `stop` | `scripts/stop.py` | No | Aggregates session events → classifies outcome (4-gate); writes recap, patterns, and the durable outbox |

- **Only `shell-guard.py` can deny** (via `{"permission": "deny"}`). The other
  three are informational — Cursor ignores their stdout. They all append to
  `~/.omnicursor/events.jsonl`.
- All hooks **fail open**: any exception degrades to allow / no-op so a hook can
  never crash Cursor.

### Active scripts vs. legacy `on_*.py`

> ⚠️ **There are two parallel hook implementations.** The **active** ones under
> `.cursor/hooks/scripts/*.py` are the only ones wired in `hooks.json`; they
> delegate to `src/omnicursor/` (via `lib/*.py` shims). The top-level
> `.cursor/hooks/on_prompt.py` / `on_shell.py` / `on_edit.py` / `on_stop.py` are
> **legacy, self-contained, and NOT wired** — they can never run in Cursor and
> survive only because `tests/test_hooks_*.py` still import them. Their behavior
> has drifted from the active scripts (e.g. `on_edit.py` runs ruff only, no
> `tsc`; `on_shell.py` lacks the DoD/dispatch tiers). Treat `scripts/*.py` as
> authoritative.

### Session outcome classification (`stop`)

`session_outcome.derive_session_outcome(status, events)` is a 4-gate tree:

1. **Failed** — failure status or error markers (`Traceback`, `…Error:`, `N FAILED`).
2. **Success** — work was done (edits / prompt classifications) **and** completion markers present.
3. **Abandoned** — no completion markers **and** duration < 60 s.
4. **Unknown** — catch-all.

---

## 5. Agent routing

17 JSON configs in `.cursor/agents/` define routing personas
(`name`, `category`, `activation_patterns`, `instructions`, `recommended_skill`).
Both the prompt hook and the library score prompts with the **same engine**,
`src/omnicursor/scoring.py` (hooks reach it through the
`.cursor/hooks/lib/agent_scoring.py` shim).

**Two merge layers** (`agents.py`): hardcoded `AGENT_CONTEXTS`
(4 categories: debugging, brainstorming, planning, ticketing) merged with the JSON
configs via `{**AGENT_CONTEXTS, **_JSON_AGENTS}`; `ALIASES` maps shorthand → canonical.

**Three (gated) scoring strategies** — note these are early-exit *tiers*, not a
flat "max of all four":

1. **Exact** substring on `explicit_triggers` (0.95) / `context_triggers` (0.80).
2. **Fuzzy** (`SequenceMatcher`, length-aware threshold) — only tried if best < 0.90.
3. **Keyword overlap** on `activation_keywords` (scaled 0.55–0.85) — only tried if best < 0.70 and ≥2 keywords overlap.

`HARD_FLOOR = 0.55`; candidates below it are discarded.

> ⚠️ **Fallback naming split.** The library returns `DEFAULT_CONTEXT`
> (`agent_name = "omnicursor-generalist"`) on no match, but the eval harness/CI
> and `polymorphic-agent.json` use `"polymorphic-agent"`. They refer to "the
> fallback" but are **not the same string** — a known inconsistency.
> Calibration constants (0.95 / 0.80 / keyword scaling / fuzzy bands) are marked
> *v0, unevaluated* in code; only `HARD_FLOOR` and the eval precision/recall
> floors are gated by `tests/test_routing_eval.py`.

---

## 6. The learning loop (patterns)

OmniCursor closes a feedback loop between routing and session outcomes:

```
prompt hook                            stop hook
───────────                            ─────────
select relevance-ranked patterns       derive session outcome (4-gate)
from ~/.omnicursor/learned_patterns    │
.json, inject as systemMessage,        ├─ on SUCCESS: reinforce the injected
emit prompt_classified event   ───────▶│   pattern_ids (weight boost, utilization)
carrying injected_pattern_ids          │   + mine new patterns from high-confidence
                                       │   prompt_classified events
                                       └─ decay stale / evict overflow patterns
```

- **Store:** `~/.omnicursor/learned_patterns.json` (record fields: `pattern_id`,
  `pattern`, `domain`, `weight`, `success_count`, `injection_count`,
  `utilization_successes`, `last_seen`, `description`).
- **Selection** (`prompt_pattern_selection.py`) scores relevance on **domain +
  description-word overlap** (threshold 0.7, cap 5) — it **ignores `weight`**.
- **Learning** (`pattern_writer.py`) holds the weight/decay/eviction constants
  (all marked *v0, unevaluated*).

> Three independent copies of `STOPWORDS`/keyword extraction exist (routing in
> `scoring.py`, selection in `prompt_pattern_selection.py`, learning in
> `pattern_writer.py`) — edit all three together.

---

## 7. Node contracts (ONEX-shaped)

Each hook is also described by a declarative **`contract.yaml`** modeled on
OmniClaude's per-node contract format, under `src/omnicursor/nodes/<node>/`.
`node_contracts.py` discovers, parses (Pydantic, `extra="allow"`), caches, and
best-effort validates them against the real `.cursor/hooks.json`.

There are **5 contracts for 4 hook events** — `beforeSubmitPrompt` is described
by **two** nodes:

| Node | `node_type` | Hook event | Blocking |
|------|-------------|------------|----------|
| `node_cursor_prompt_orchestrator` | ORCHESTRATOR_GENERIC | `beforeSubmitPrompt` | No |
| `node_cursor_pattern_injection_compute` | COMPUTE | `beforeSubmitPrompt` | No |
| `node_cursor_shell_guard_effect` | EFFECT_GUARD | `beforeShellExecution` | **Yes** |
| `node_cursor_file_edit_effect` | EFFECT_POST_EDIT | `afterFileEdit` | No |
| `node_cursor_session_outcome_orchestrator` | ORCHESTRATOR_GENERIC | `stop` | No |

### Dual execution model

Both the runtime hook scripts and the importable node surface delegate to the
**same** shared library modules (`file_edit`, `shell_guard`, `session_outcome`,
`scoring`, …):

- **Runtime:** Cursor executes the stdlib-only `.cursor/hooks/scripts/*.py`, which
  insert `src/` (and `.cursor/hooks/lib/`) onto `sys.path` and `import omnicursor.*`
  directly. They are thin entrypoints — **not** duplicated logic.
- **In-process surface:** each node's `node.py` → `handler.py` → `handlers/*.py` →
  typed `models/*.py` re-runs the same delegation for tests/CI/scripting.

The genuinely **duplicated, self-contained** copies of the logic live only in the
**legacy `.cursor/hooks/on_*.py`** (see §4) — and those have drifted from the
active scripts, with no automated parity guard.

> Known field-mapping gaps in the in-process node surface (document, don't mistake
> for bugs): the shell-guard soft-warn message and the file-edit `tsc` findings
> are computed by the shared libs but **dropped** by the node output models; the
> session-outcome contract's `durable_outbox`/`injected_pattern_ids` obligation
> is fulfilled by the `stop` hook's `session_outbox` writer, not the node's Python output.

---

## 8. Event emission

> **Two different files are easy to conflate:**
> `~/.omnicursor/events.jsonl` is the hooks' raw **audit log** (every hook
> appends to it). `~/.omnicursor/outbox.jsonl` is the **durable session-outcome
> feed** written by `session_outbox.write_session_outcome` from the `stop` hook —
> a local, append-only record kept for replay/audit.

Emission onto the ONEX bus is **not** a Cursor-specific transport. The hooks emit
best-effort through a stdlib Unix-socket client (`emit_client.send_event` →
`~/.omnicursor/emit.sock`); that socket is owned by the **shared platform emit
daemon** (omnimarket `node_emit_daemon` — the same daemon OmniClaude uses), which
is responsible for queueing, spooling, and publishing to Kafka. The hook stays
stdlib-only and never talks to Kafka itself.

```
hook ──send_event({event_type, payload})──▶ emit.sock ──▶ shared emit daemon ──▶ Kafka
                                                            (omnimarket node_emit_daemon)
```

- **Best-effort, non-blocking:** if the socket is missing or the daemon is absent,
  `send_event` returns `False` and the hook continues — emission never blocks Cursor.
- **No bespoke stack:** there is no Cursor-owned sidecar/drainer/publisher. The wire
  protocol (`{"event_type", "payload"}\n` → `{"status": "queued", "event_id"}\n`) is
  the shared OmniClaude/omnimarket daemon protocol, so OmniCursor inherits whatever
  transport the platform lands (see OMN-13213) without any Cursor-side change.
- **Durable outbox is separate:** the `stop` hook's `outbox.jsonl` record persists
  locally regardless of whether the daemon is running.

---

## 9. OmniMarket bridge & MCP

OmniCursor reaches OmniNode by invoking **omnimarket** nodes — not by calling
omniintelligence service APIs directly.

- **Bridge** (`omnimarket_bridge.py`): runs `python -m omnimarket.nodes.<node>`
  as a **subprocess**, injecting `{OMNIMARKET_ROOT}/src` into `PYTHONPATH`.
  It **never raises** — failures are encoded in a `BridgeResult`.
- **Needs a local omnimarket checkout.** Set `OMNIMARKET_ROOT` to point at it; the
  bridge also falls back to an `omnimarket-main/` directory in the repo root if one
  exists (dev convenience). On a clean clone neither is present, so bridge/MCP calls
  error until `OMNIMARKET_ROOT` is set. (The in-process handler fallback mentioned
  in older docs is **not implemented** — subprocess only.)
- **MCP server** (`python -m omnicursor.mcp`, stdio, name `omnicursor-omnimarket`)
  exposes three tools: `run_local_review`, `run_ticket_pipeline`, `run_ci_watch`.
  Needs the optional `mcp` extra (`pip install -e ".[mcp]"`); `run_ci_watch`
  needs the `gh` CLI.

---

## 10. Intelligence options (A / B)

All networked tiers are **opt-in**; the plugin works fully offline.

| Option | What | Gate |
|--------|------|------|
| **A** | Local pattern learning at `~/.omnicursor/learned_patterns.json` | Always on, offline |
| **B** | HTTP pull from omniintelligence (`sync/pattern_sync.py`) | `OMNICURSOR_PATTERN_SYNC_HTTP` (**default off**), `OMNIINTELLIGENCE_URL` |

> Event emission onto the bus (via the shared platform emit daemon, §8) is a
> separate opt-in tier — active only when the daemon owns `~/.omnicursor/emit.sock`.

> The prompt hook *also* fetches patterns over HTTP at prompt-time using a
> **different** variable, `INTELLIGENCE_SERVICE_URL` (with a local-cache
> fallback). `INTELLIGENCE_SERVICE_URL` (per-prompt fetch) and
> `OMNIINTELLIGENCE_URL` (session-end sync) are read by different code paths —
> don't confuse them.

---

## 11. Local state (`~/.omnicursor/`)

| Path | Purpose |
|------|---------|
| `events.jsonl` | Raw hook event audit log |
| `sessions/<conversation_id>.json` | Per-session facts (ticket ids, `ci_passing`, routing) |
| `sessions/current.json` | Most recent session pointer (fake SessionStart) |
| `learned_patterns.json` | Option A pattern store |
| `outbox.jsonl` | Durable session-outcome record (`schema_version: omnicursor.session_outcome.v1`) |
| `emit.sock` | Unix socket for hook event emission, owned by the shared platform emit daemon (§8) |
| `last-recap.md` | Pending recap prepended to the next prompt |

---

## 12. Packaging

- **Python package:** setuptools `src/` layout, runtime deps `pydantic` + `pyyaml`,
  extras `[dev]` (pytest) and `[mcp]`. Version `0.1.0`. Only
  `nodes/*/contract.yaml` is bundled as package data — the `.cursor/` surfaces
  ship via the plugin symlink, **not** via pip.
- **Cursor plugin:** `scripts/install-plugin.sh` symlinks the repo into
  `~/.cursor/plugins/local/omnicursor`. Two manifests exist
  (`.cursor-plugin/plugin.json` is the official one; root `cursor-plugin.json` is
  a companion) and their versions must be kept in sync (`tests/test_plugin_manifest.py`).

---

## Source-of-truth hierarchy

When documents disagree:

1. **Actual current codebase behavior**
2. This file and the other docs under `docs/` — repo conventions & architecture
3. `omnicursor-team-guidance.md` — demo-focused guidance (local; gitignored)
4. `omniclaude-main/` — read-only reference library (gitignored; absent from a clean clone)

---

**See also:** [`CURRENT_STATE.md`](./CURRENT_STATE.md) ·
[`QUICKSTART.md`](./QUICKSTART.md) · [`INDEX.md`](./INDEX.md)

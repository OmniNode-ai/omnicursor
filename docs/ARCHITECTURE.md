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

```text
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
| **Hooks** | `.cursor/hooks/scripts/*.py` (7) | Deterministic, stdlib-only lifecycle scripts |
| **Library** | `src/omnicursor/` | Routing, scoring, skills, compliance, contracts, bridge — for **pytest/CI/scripting only** |

> **Key boundary:** the hooks are **stdlib-only** and must run without a
> virtualenv. The active scripts reach shared logic by inserting `.cursor/hooks/lib/`
> (and `src/` where needed) onto `sys.path` and importing the lib modules
> (`_common`, `context_injection`, …) and `omnicursor.*` **directly** — those are the
> single source of truth, the scripts are thin entrypoints. The previous duplicated
> `.cursor/hooks/on_*.py` set was deleted in the W4 alignment. See [§4 Hooks](#4-hooks)
> and [§7 Node contracts](#7-node-contracts-onex-shaped).

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

Seven Cursor lifecycle events are wired in `.cursor/hooks.json` to
**stdlib-only** scripts:

| Event | Active script | Can block? | Role |
|-------|---------------|------------|------|
| `sessionStart` | `scripts/session-start.py` | No | Session init + daemon-ensure + emit `session-started`; **injects** session-level context (baseline patterns + delegation rule + prior session) via `additional_context` |
| `beforeSubmitPrompt` | `scripts/user-prompt-submit.py` | No | Classifies the prompt → best agent; emits classification + relevant patterns for backend learning. **Block-only** (`{continue, user_message}`) — cannot inject |
| `beforeShellExecution` | `scripts/shell-guard.py` | **Yes** | Two-tier guard: **9 HARD_BLOCK** (deny) + **12 SOFT_WARN** (allow + warning); optional DoD/dispatch gates. Output `{permission: allow\|deny\|ask, user_message, agent_message}` |
| `afterFileEdit` | `scripts/post-edit.py` | No | Diagnostic `ruff check` (`.py`) and `tsc --noEmit` (`.ts`) — **never `--fix`**, never modifies files; emits `tool-executed` |
| `postToolUse` | `scripts/post-tool-use.py` | No | **Refreshes** injected context via `additional_context` (patterns for the tool's inferred domain); emits `tool-executed` |
| `stop` | `scripts/stop.py` | No | Aggregates session events → classifies outcome (4-gate); writes recap, patterns, and the durable outbox (loop-end) |
| `sessionEnd` | `scripts/session-end.py` | No | Emit `session-ended` (true conversation close, complements `stop`); fire-and-forget |

- **Only `shell-guard.py` can deny** (via `{"permission": "deny"}`).
- **Injection** happens only at `sessionStart.additional_context` (initial) and
  `postToolUse.additional_context` (refresh) — Cursor's `beforeSubmitPrompt` output is
  block-only (`{continue, user_message}`) and a `systemMessage` there is silently ignored.
  Shared context-assembly lives in `.cursor/hooks/lib/context_injection.py`.
- The observational hooks append to `~/.omnicursor/events.jsonl` and emit best-effort
  events via the shared daemon.
- All hooks **fail open**: any exception degrades to allow / no-op so a hook can
  never crash Cursor.
- **Kill-switch (A6):** `OMNICURSOR_HOOKS_DISABLE=1` **or** the file marker
  `~/.omnicursor/hooks-disabled` short-circuits all 7 hooks first thing in
  `main()` — before stdin, daemon-ensure, pattern fetch/sync, local logging,
  emission, and injection writes. Disabled outputs are benign (`shell-guard` →
  `{"permission": "allow"}` — a disabled guard never blocks; `user-prompt-submit`
  → `{"continue": true}`; injection hooks → `{}`). `OMNICURSOR_HOOKS_MASK`
  (comma-separated allowlist of hook short names, e.g. `"prompt,shell"`)
  enables only the named hooks; unset = all on. Gate logic:
  `lib/_common.py::hooks_disabled()/hook_enabled()` (mirrors omniclaude's
  `_hooks_disabled`).

### Hook script layout

All hooks live under `.cursor/hooks/scripts/*.py` (the only set wired in
`hooks.json`), delegating to shared logic in `.cursor/hooks/lib/*.py`
(`_common`, `context_injection`, `emit_client`, `pattern_loader`,
`prompt_pattern_selection`, `pattern_sync`) and, where needed, to `src/omnicursor/`.
The previous parallel top-level `on_*.py` set was deleted in the W4 hook alignment —
`scripts/*.py` is the single source.

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

```text
sessionStart / postToolUse             prompt hook               stop hook
──────────────────────────             ───────────               ─────────
inject relevance-ranked patterns       classify prompt →         derive outcome (4-gate)
from ~/.omnicursor/learned_patterns    emit prompt_classified    │
.json via additional_context           carrying relevant  ──────▶├─ on SUCCESS: reinforce the
(sessionStart = baseline,              pattern_ids               │   pattern_ids (weight, utilization)
 postToolUse = refresh)                                          │   + mine new patterns
                                                                 └─ decay stale / evict overflow
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

There are **7 contracts across 7 hook events**:

| Node | `node_type` | Hook event | Blocking |
|------|-------------|------------|----------|
| `node_cursor_pattern_injection_compute` | COMPUTE | `sessionStart` | No |
| `node_cursor_prompt_orchestrator` | ORCHESTRATOR_GENERIC | `beforeSubmitPrompt` | No |
| `node_cursor_shell_guard_effect` | EFFECT_GUARD | `beforeShellExecution` | **Yes** |
| `node_cursor_file_edit_effect` | EFFECT_POST_EDIT | `afterFileEdit` | No |
| `node_cursor_tool_use_compute` | COMPUTE | `postToolUse` | No |
| `node_cursor_session_outcome_orchestrator` | ORCHESTRATOR_GENERIC | `stop` | No |
| `node_cursor_session_end_effect` | EFFECT | `sessionEnd` | No |

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

```text
hook ──send_event({event_type, payload})──▶ emit.sock ──▶ shared emit daemon ──▶ Kafka
                                                            (omnimarket node_emit_daemon)
```

- **Best-effort, timeout-bound:** if the socket is missing or the daemon is absent,
  `send_event` returns `False` and the hook continues — emission is soft-fail only,
  waiting at most `OMNICURSOR_EMIT_TIMEOUT` (default 0.5s) on a live socket.
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
| **B** | HTTP pull from omniintelligence (`sync/pattern_sync.py`) | `OMNICURSOR_PATTERN_SYNC_HTTP` (**default off**), `INTELLIGENCE_SERVICE_URL` |

> Event emission onto the bus (via the shared platform emit daemon, §8) is a
> separate opt-in tier — active only when the daemon owns `~/.omnicursor/emit.sock`.

> Both HTTP paths — the per-prompt fetch (`lib/context_injection.py`) and the
> session-end sync (`sync/pattern_sync.py`) — are single-sourced on
> `INTELLIGENCE_SERVICE_URL` (default `http://localhost:18091`). The old
> `OMNIINTELLIGENCE_URL` name is still honored by the sync path as a
> **deprecated fallback for one release** — migrate to
> `INTELLIGENCE_SERVICE_URL`.

---

## 11. Local state (`~/.omnicursor/`)

| Path | Purpose |
|------|---------|
| `events.jsonl` | Raw hook event audit log |
| `sessions/<conversation_id>.json` | Per-session facts (ticket ids, `ci_passing`, routing) |
| `sessions/current.json` | Most recent session pointer (written by the `sessionStart` hook) |
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

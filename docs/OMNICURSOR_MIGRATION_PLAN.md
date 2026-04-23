# OmniCursor Migration Plan
## omniclaude → omnicursor

**Status:** Foundation-first (Phase 1 hooks delivered). Sponsor splits **this repo** (hooks + `src/omnicursor`) from **omnimarket MCP / integration** work — see [SPONSOR_ALIGNMENT_2026-04-16.md](./dev/SPONSOR_ALIGNMENT_2026-04-16.md).
**Last updated:** 2026-04-22

**Philosophy:** Ship a **small, strong Cursor-native core** (hooks, routing, curated agents/skills, stub ONEX contracts) and grow **only when a concrete workflow needs it**. `omniclaude-main/` is a **patterns reference**, not a checklist to empty.

**Port track (agents, skills, ONEX nodes & contracts):** See [MIGRATION_PHASES_HANDOFF.md](./dev/MIGRATION_PHASES_HANDOFF.md) — **excludes** hooks/Kafka/Linear/MCP/pattern-write work. This document is the **roadmap** for hooks + optional expansion tracks; it does **not** commit to omniclaude surface parity.

---

## Sponsor alignment (2026-04-16)

This plan describes how OmniCursor relates to **omniclaude-style** behavior on Cursor. **Capstone scope** stays narrow per sponsor feedback; **full omniclaude parity is not a goal** — only a **foundation** plus optional add-ons:

- **Hooks:** Four events are the correct ceiling; only `beforeShellExecution` truly *blocks*. Workarounds (fake SessionStart, rules, MCP advisory) are intentional — see [SPONSOR_ALIGNMENT_2026-04-16.md](./dev/SPONSOR_ALIGNMENT_2026-04-16.md).
- **OmniNode bridge (sponsor — separate integration track):** Prefer **`omnimarket` nodes** (subprocess `python -m` or in-process handlers). **Do not** target direct omniintelligence service APIs or broken `onex run <contract.yaml>` for that bridge. This repo’s checklist does **not** include that MCP bridge unless explicitly in scope.
- **Patterns (capstone):** Persistence **local** (file + team-owned PG); hooks here expose **optional** HTTP pull (`OMNICURSOR_PATTERN_SYNC_HTTP`, dev-only), not authoritative writes to intelligence.
- **Docker:** Keep Compose **minimal**; **local-first** runtime before infra expansion.

---

## Background

OmniCursor ships a **deliberate foundation**: 4 Cursor hooks, JSON-backed **agents** (order-of ~17 configs including Cursor-specific ones), **~12 methodology skills** today (design ceiling on the order of **~17 curated skills** — grow only when needed), **five** ONEX-shaped node contracts under `src/omnicursor/nodes/` (hooks + read-side pattern compute), and rules. **omniclaude** has a much larger surface (many agents, 80+ skills, many nodes). That scale is **reference**, not a target.

| Dimension | OmniCursor (foundation) | omniclaude (reference scale) |
|---|---|---|
| Hook event types | 4 (mapped from 8 CC concepts) | 8 |
| Agents | ~17 JSON + hardcoded routing categories | ~53 |
| Skills | ~12 (ceiling ~17 curated) | 80+ |
| ONEX nodes | **5** contracts (4 hooks + pattern read compute); stubs + thin `handler.py` | 80+ |
| Kafka emission | Optional Unix socket (`emit_client`); `~/.omnicursor/events.jsonl` | Full publisher |
| Linear / DoD | Config + hooks where implemented | Full pipeline |
| Patterns | Local file + optional HTTP pull (dev) | Broader stack |

**Strategic goal:** Harden **Cursor-native execution** (rules, agents JSON, hooks, small library). Add agents, skills, or node bodies **incrementally** when a feature or demo requires them — not by porting omniclaude wholesale.

---

## Hook Surface Mapping

Claude Code exposes 8 lifecycle hook types. Cursor exposes 4. The table below documents how each Claude Code hook maps to Cursor:

| Claude Code hook | Cursor equivalent | Strategy |
|---|---|---|
| `SessionStart` | `beforeSubmitPrompt` (first-prompt flag) | Detect first prompt via session state file; run init logic once |
| `UserPromptSubmit` | `beforeSubmitPrompt` | Already mapped — expand with Kafka emit + delegation bridge |
| `PreToolUse (Bash)` | `beforeShellExecution` | Already mapped — add DoD gate, dispatch claim check |
| `PreToolUse (Agent/Task)` | No native equivalent | Inject dispatch guard constraints via always-on rule; enforce in `beforeSubmitPrompt` |
| `PostToolUse` | `afterFileEdit` + rules | `afterFileEdit` covers write tools; shell post-audit via `beforeShellExecution` echo-back or rules-only |
| `Stop` | `stop` | Already mapped — expand session accumulator + Kafka emission |
| `SessionEnd` | `stop` | Merge into `stop` hook |
| `PreCompact` | No native equivalent | Rules-only: inject compaction guidance in always-on rule `00-omninode-concepts.mdc` |

> **Biggest constraint:** Cursor has no `PreToolUse`/`PostToolUse` equivalents, so the dispatch-claim guard and post-audit hooks that gate `Edit`/`Write`/`Bash` in omniclaude cannot be implemented at the same fidelity. Mitigation: encode those constraints as always-on rules and rely on `beforeShellExecution` for the Bash surface.

---

## Phases

### Phase 1 — Hook surface (8 → 4 Cursor events)

**Goal:** Map all 8 Claude Code hook **concepts** onto Cursor’s 4 hook events, with no regression on existing guards. This is **behavioral coverage on Cursor**, not “identical omniclaude hook code.”

**Status (2026-04-20):** Delivered in-tree (hooks under `.cursor/hooks/scripts/`).

**Deliverables:**

- Expand `scripts/user-prompt-submit.py`:
  - Add first-prompt detection (session state file at `~/.omnicursor/sessions/{id}.json`)
  - Emit `onex.cmd.omnicursor.cursor-hook-event.v1` via Unix socket client (see Phase 5)
  - Add delegation bridge: publish complex prompts to Kafka `node_delegation_orchestrator`
- Expand `scripts/shell-guard.py`:
  - Add DoD gate: block Linear status transitions unless CI-passing signal is present
  - Add dispatch claim check: require registered claim before destructive edits
- Expand `scripts/stop.py`:
  - Emit `onex.evt.omnicursor.session-ended.v1` with outcome classification
  - Optional: HTTP pattern refresh when `OMNICURSOR_PATTERN_SYNC_HTTP` is set (Phase 7 / dev only)
- Add always-on rule section to `00-omninode-concepts.mdc` covering compaction guidance and dispatch guard constraints

**Implemented as:**

| Deliverable | Location |
|-------------|----------|
| Session state JSON + first-prompt merge | `.cursor/hooks/scripts/user-prompt-submit.py`, `lib/_common.py` (`merge_session_json`, `read_session_json`) |
| Unix socket emit client | `.cursor/hooks/lib/emit_client.py` (`OMNICURSOR_EMIT_SOCKET`, default `~/.omnicursor/emit.sock`) |
| Hook + delegation emit types | `onex.cmd.omnicursor.cursor-hook-event.v1`, `onex.cmd.omnicursor.node-delegation-request.v1` (when delegation is required) |
| DoD + dispatch config | `.cursor/hooks/config/dod_enforcement.json`; bypass env: `OMNICURSOR_DOD_BYPASS`, `OMNICURSOR_DISPATCH_BYPASS` |
| Session end emit | `.cursor/hooks/scripts/stop.py` → `onex.evt.omnicursor.session-ended.v1` |
| Optional HTTP pattern pull (dev) | `lib/pattern_sync.py`, `src/omnicursor/sync/pattern_sync.py` — runs on **stop** only if `OMNICURSOR_PATTERN_SYNC_HTTP` is set (default **off**, per sponsor) |
| Always-on rule updates | `.cursor/rules/00-omninode-concepts.mdc` |

**Follow-up:** Phase 5 emit **daemon** (listening socket) is optional for many demos. Hooks already **emit** via `emit_client` (no-op until something listens). Sponsor-priority **omnimarket MCP** “Cursor talks to OmniNode” is **outside** this repo’s default checklist — see sponsor doc.

**Capstone bridge:** MCP → **`omnimarket`** (`python -m` or in-process), not direct omniintelligence HTTP for that demo path.

---

### Phase 2 — Agent layer (foundation + optional adds)

**Foundation (default):** Keep the existing `.cursor/agents/*.json` set (~17 files), **dynamic loading** in `src/omnicursor/agents.py`, hook routing in sync with library scoring, and **tests green**. That is enough to build on.

**Optional (only if needed):** Add a new JSON agent when a capstone or product workflow needs it; use omniclaude YAML/JSON as **copy-paste reference** for fields (`name`, `description`, `category`, `activation_patterns`, `instructions`, `recommended_skill`). Do **not** treat “match omniclaude’s ~53 agents” as success criteria.

---

### Phase 3 — Skill layer (foundation + optional adds)

**Foundation (default):** Maintain **~12 methodology skills** today; treat **~17 curated skills** as a **soft ceiling** unless the team explicitly widens scope. Every shipped skill needs `skills/<name>.md`, `compliance.py` entries (3–5 checks), and tests — see CI compliance step.

**Optional (only if needed):** Port additional OmniClaude `SKILL.md` content in small batches. Prefer **Bucket 1** (no external deps); **Bucket 3** skills must stay explicitly manual/dry-run if they mention Kafka, Linear, or other integrations — never silent fakes.

---

### Phase 4 — ONEX nodes (foundation stubs → real when justified)

**Foundation (default):** Under `src/omnicursor/nodes/` there are **five** contracts: the four lifecycle hook nodes plus **`node_cursor_pattern_injection_compute`** (read-side pattern selection for prompts; **no writes**). Each has `contract.yaml` + thin `handler.py`; tests cover contracts, hook binding parity, and pattern read logic. **Harden runtime behavior further** only when a demo or integration needs it — not to mirror omniclaude’s full node catalog.

**Optional (only if needed):** Additional nodes (e.g. routing compute, delegation orchestrator, pattern injection compute) follow the same rule: add when there is a concrete consumer; align pattern **read** paths with local/file contracts; **writes** and bus semantics stay with the persistence / infra tracks.

| Stub (existing) | Type | Emits (declared) |
|---|---|---|
| `node_cursor_prompt_orchestrator` | `NodeOrchestrator` | `onex.evt.omnicursor.prompt-submitted.v1` |
| `node_cursor_shell_guard_effect` | `NodeEffect` | `onex.evt.omnicursor.shell-executed.v1` |
| `node_cursor_file_edit_effect` | `NodeEffect` | `onex.evt.omnicursor.file-edited.v1` |
| `node_cursor_session_outcome_orchestrator` | `NodeOrchestrator` | `onex.evt.omnicursor.session-ended.v1` |
| `node_cursor_pattern_injection_compute` | `COMPUTE` (read) | Local `learned_patterns.json` only; hook still `user-prompt-submit.py` |

---

### Phase 5 — Kafka / event emission (optional infra)

**Goal:** When the team needs it, wire hooks to a bus via Unix socket + daemon, **similar in spirit** to omniclaude’s emit pattern — not a prerequisite for the foundation.

**Capstone note (sponsor):** **Do not** block hook work in this repo on the full bus. **Hooks already call** `emit_client` (`.cursor/hooks/lib/emit_client.py`). Omnimarket/MCP demos and daemon expansion are **coordinated** across the team.

**Deliverables:**

- Port the Unix socket emit daemon from `omniclaude` reference into `src/omnicursor/publisher/` (optional for capstone)
- Client already lives in `.cursor/hooks/lib/emit_client.py` (stdlib)
- Topic naming when publishing: `onex.{kind}.omnicursor.{event-name}.v1` (parallel to omniclaude’s `onex.{kind}.omniclaude.*`)
- Consumers may include omnimarket projections — align topic contracts with that repo, not only omniintelligence

---

### Phase 6 — Linear Ticket Pipeline (Bucket 3)

**Goal:** Port ticket context injection and DoD enforcement using Cursor MCP (Linear already enabled in `settings.json`).

**Deliverables:**

- `scripts/user-prompt-submit.py`: detect Linear ticket IDs in prompt (regex `[A-Z]+-\d+`) → fetch ticket via Linear MCP → inject context into `systemMessage`
- `scripts/shell-guard.py`: DoD gate — block Linear status transitions unless CI-passing signal present in session state
- Port `omniclaude/plugins/onex/hooks/config/dod_enforcement.yaml` to `OmniCursor/.cursor/hooks/config/dod_enforcement.yaml`
- Add `.cursor/rules/16-linear-create.mdc` — guidance for creating Linear tickets
- Add `.cursor/rules/17-linear-consume.mdc` — guidance for consuming/transitioning Linear tickets

---

### Phase 7 — Pattern lifecycle (revised for sponsor)

**Long-term (optional):** Richer pattern loop (events → store → patterns in context) if the team invests in that stack — **not** a foundation requirement.

**Capstone goal:** **Local-first** pattern store (file today; **PostgreSQL** per team plan). **Writes to upstream omniintelligence are out of capstone scope** (year-2). Optional **HTTP GET** refresh exists for dev (`OMNICURSOR_PATTERN_SYNC_HTTP=1` on stop); default is **off**.

**Deliverables:**

- `src/omnicursor/sync/pattern_sync.py` — optional GET to omniintelligence for **dev experimentation only**
- Authoritative capstone path: team-defined **local / PG** persistence; hooks adapt read path (`pattern_loader.py` / `learned_patterns.json` or successor) when that contract exists
- Optional background sync daemon — **not** a prerequisite in this repo for an omnimarket integration demo

---

## Execution Order

**Parallel track:** Omnimarket MCP bridge per sponsor — **not** step 1 of this repo’s foundation. See [SPONSOR_ALIGNMENT_2026-04-16.md](./dev/SPONSOR_ALIGNMENT_2026-04-16.md).

**Port track:** Keep **Phase 2–4** green at **foundation** depth first (current agents/skills/nodes + tests). Add agents, skills, or node behavior **incrementally** per [MIGRATION_PHASES_HANDOFF.md](./dev/MIGRATION_PHASES_HANDOFF.md). Phases **5–7** are **optional** and infra-driven.

**Full repo:** Phase **1** is the maintained hook base. Phases **6–7** and **5** ship only when those tracks are explicitly prioritized.

```
Foundation (default):     Phase 1 (hooks) + current agents/skills/node stubs + CI

Optional expansion:       Phase 2 / 3 / 4  — add only when needed  →  MIGRATION_PHASES_HANDOFF.md

Hooks + Linear:           Phase 6 (when assigned)
Kafka + consumers:        Phase 5 (when team commits)
Patterns + PG:            Phase 7 (with persistence track)
Omnimarket MCP bridge:    integration track (sponsor)
```

### Recommended order (**foundation**)

1. Keep **Phase 1** hooks and session/emit behavior healthy.
2. Keep **Phase 2–3** at foundation depth: routing tests, compliance, and docs updated when you touch agents or skills.
3. **Phase 4:** deepen stub nodes **when** a demo or contract needs it.

### Optional order (**when assigned**)

1. **Phase 6** — Linear in hooks + rules (builds on Phase 1).
2. **Phase 7** — Pattern store + optional dev HTTP pull.
3. **Phase 5** — Bus + consumers when infra is ready.

---

## Key Constraints

- `omniclaude-main/` is **read-only reference** — never modify it
- Hook scripts must use **Python stdlib only** (no pip dependencies)
- `post-edit.py` / `on_edit.py` runs `ruff check` diagnostically — never `--fix`, never modifies files
- All Bucket 3 skills must be clearly labeled; do not silently simulate Linear/Kafka calls
- ONEX node invariants from `omnibase_core` apply: unidirectional flow `EFFECT → COMPUTE → REDUCER → ORCHESTRATOR`, nodes < 100 lines, all behavior declared in `contract.yaml`
- **Do not build capstone on** `onex run <contract.yaml>` until omnimarket routing validation is fixed upstream; use `python -m omnimarket.nodes.<node>` or in-process handlers
- **Do not** claim rules “block” tool calls — they guide; only the shell hook *denies*

# OmniCursor Migration Plan
## omniclaude → omnicursor

**Status:** Planning (Phase 1 hooks delivered). Sponsor splits **this repo** (hooks + `src/omnicursor`) from **omnimarket MCP / integration** work — see [SPONSOR_ALIGNMENT_2026-04-16.md](./dev/SPONSOR_ALIGNMENT_2026-04-16.md).
**Last updated:** 2026-04-21

**Port track (agents, skills, ONEX nodes & contracts):** If your scope is **only** porting those artifacts from OmniClaude, follow [MIGRATION_PHASES_HANDOFF.md](./dev/MIGRATION_PHASES_HANDOFF.md) — it **excludes** hooks/Kafka/Linear/MCP/pattern-write work. This document below remains the **full** phase map for the repository and team.

---

## Sponsor alignment (2026-04-16)

Long-term this plan still describes **omniclaude → Cursor** parity. **Capstone scope** is narrower per sponsor feedback:

- **Hooks:** Four events are the correct ceiling; only `beforeShellExecution` truly *blocks*. Workarounds (fake SessionStart, rules, MCP advisory) are intentional — see [SPONSOR_ALIGNMENT_2026-04-16.md](./dev/SPONSOR_ALIGNMENT_2026-04-16.md).
- **OmniNode bridge (sponsor — separate integration track):** Prefer **`omnimarket` nodes** (subprocess `python -m` or in-process handlers). **Do not** target direct omniintelligence service APIs or broken `onex run <contract.yaml>` for that bridge. This repo’s checklist does **not** include that MCP bridge unless explicitly in scope.
- **Patterns (capstone):** Persistence **local** (file + team-owned PG); hooks here expose **optional** HTTP pull (`OMNICURSOR_PATTERN_SYNC_HTTP`, dev-only), not authoritative writes to intelligence.
- **Docker:** Keep Compose **minimal**; **local-first** runtime before infra expansion.

---

## Background

OmniCursor already has a solid scaffold: 4 Cursor hooks, 17 agents, 12 skills, 4 stub ONEX nodes, and 11 rules. The gap vs omniclaude is:

| Dimension | OmniCursor (current) | omniclaude |
|---|---|---|
| Hook event types | 4 | 8 |
| Agents | 17 (see note re: plan vs extra Cursor-specific agents) | 53 |
| Skills | 12 | 80+ |
| ONEX nodes | 4 stubs | 80+ real implementations |
| Kafka emission | Optional Unix socket (`emit_client`); logs to `~/.omnicursor/events.jsonl` | Full aiokafka publisher |
| Linear integration | settings.json enabled | Full DoD enforcement pipeline |
| Pattern learning | `learned_patterns.json` + hook load; capstone writes local / PG | File + omniintelligence REST (full stack) |

The strategic goal is to close the gap using **Cursor-native execution** (`.cursor/rules/`, `.cursor/agents/`, `.cursor/hooks/`, Cursor MCP). Sponsor near-term capstone priority for **integration** is **MCP → omnimarket**; this repo focuses on **hook + library** depth (agents, skills, contracts) without absorbing unrelated bridge or persistence work by default.

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

### Phase 1 — Hook Surface Parity

**Goal:** Cover all 8 Claude Code hook types using Cursor's 4, with no regression on existing guards.

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

### Phase 2 — Agent Coverage (17 → 53)

**Goal:** Port all omniclaude agents to `.cursor/agents/*.json` format.

The omniclaude agent YAML → OmniCursor JSON mapping is already established. The 36 missing agents fall into these categories:

| Category | Examples | Count |
|---|---|---|
| Skill orchestrators | ticket-pipeline, merge-sweep, pr-review, autopilot, ci-watch, golden-chain | ~15 |
| Channel adapters | slack, discord, email, telegram, sms | 5 |
| Specialized | adversarial-pipeline, baseline, build-loop, bus-audit, compliance-sweep, aislop-sweep | ~10 |
| Debugging/QA | debug-database, debug-intelligence, security-audit, performance | 4 |
| Misc | content-summarizer, repository-crawler, research, documentation-architect | 4 |

Each agent JSON must include: `name`, `description`, `category`, `activation_patterns` (with `explicit_triggers`, `context_triggers`, `activation_keywords`), `instructions`, `recommended_skill`.

**Deliverables:** 36 new `.cursor/agents/*.json` files.

---

### Phase 3 — Skill Coverage (12 → 80+)

**Goal:** Port omniclaude SKILL.md files to OmniCursor `skills/*.md` with compliance registry entries.

Prioritized by bucket:

| Bucket | Count | Notes |
|---|---|---|
| Bucket 1 (no external deps) | ~60 | Direct port from `omniclaude/plugins/onex/skills/*/SKILL.md` |
| Bucket 2 (local files only) | ~10 | Port with file-path adjustments |
| Bucket 3 stubs (external deps) | ~10 | Port as dry-run/manual-steps only, clearly labeled |

Each skill requires:
1. `skills/<name>.md` — methodology document
2. Compliance registry entry in `compliance.py` with 3–5 keyword checks
3. Corresponding `.cursor/rules/<n>-<name>.mdc` if the skill needs auto-activation on keyword match

---

### Phase 4 — Real ONEX Node Implementations

**Goal:** Upgrade 4 stub nodes to real `omnibase_core` implementations; add critical missing nodes.

**Existing stubs to implement:**

| Node | Type | Emits |
|---|---|---|
| `node_cursor_prompt_orchestrator` | `NodeOrchestrator` | `onex.evt.omnicursor.prompt-submitted.v1` |
| `node_cursor_shell_guard_effect` | `NodeEffect` | `onex.evt.omnicursor.shell-executed.v1` |
| `node_cursor_file_edit_effect` | `NodeEffect` | `onex.evt.omnicursor.file-edited.v1` |
| `node_cursor_session_outcome_orchestrator` | `NodeOrchestrator` | `onex.evt.omnicursor.session-ended.v1` |

**New nodes to add:**

| Node | Type | Purpose |
|---|---|---|
| `node_cursor_agent_routing_compute` | `NodeCompute` | Fuzzy + optional LLM routing (port of omniclaude's `node_agent_routing_compute`) |
| `node_cursor_delegation_orchestrator` | `NodeOrchestrator` | Delegates complex prompts to Kafka for multi-agent tasks |
| `node_cursor_pattern_injection_compute` | `NodeCompute` | **Long-term:** inject patterns into hook context. **Capstone:** align with **local / PG** store + optional omnimarket helpers — **not** raw omniintelligence API as the only path |

Each node requires: `contract.yaml`, `handler.py`, `__init__.py`, unit tests.

---

### Phase 5 — Kafka / Event Emission (long-term parity)

**Goal:** Wire hooks to a bus via Unix socket + daemon, matching omniclaude’s `emit_client_wrapper` pattern when full ONEX streaming is required.

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

**Long-term goal:** Full omniclaude-style loop (events → intelligence → patterns in context).

**Capstone goal:** **Local-first** pattern store (file today; **PostgreSQL** per team plan). **Writes to upstream omniintelligence are out of capstone scope** (year-2). Optional **HTTP GET** refresh exists for dev (`OMNICURSOR_PATTERN_SYNC_HTTP=1` on stop); default is **off**.

**Deliverables:**

- `src/omnicursor/sync/pattern_sync.py` — optional GET to omniintelligence for **dev experimentation only**
- Authoritative capstone path: team-defined **local / PG** persistence; hooks adapt read path (`pattern_loader.py` / `learned_patterns.json` or successor) when that contract exists
- Optional background sync daemon — **not** a prerequisite in this repo for an omnimarket integration demo

---

## Execution Order

**Parallel track:** Omnimarket MCP bridge per sponsor — **not** step 1 of this repo’s hook/library checklist. See [SPONSOR_ALIGNMENT_2026-04-16.md](./dev/SPONSOR_ALIGNMENT_2026-04-16.md).

**Port track only:** Phases **2, 3, 4** (agents, skills, nodes) can overlap in batches — see [MIGRATION_PHASES_HANDOFF.md](./dev/MIGRATION_PHASES_HANDOFF.md). No dependency on Phase 5–7 for that checklist.

**Full repo:** Phases 1, 2, and 3 can proceed in parallel **in this repo**. Phase 5 is not required to finish hook/library milestones here. Phase 6 depends on Phase 1. Phase 7 read path: **file now**; **PG** when the team defines the store contract.

```
Port (agents / skills / nodes):  Phase 2 ──► Phase 3 ──► Phase 4   →  MIGRATION_PHASES_HANDOFF.md

Hooks + Linear:                  Phase 1 ──────────────────────► Phase 6
Kafka daemon + bus consumers:    Phase 5 (team / infra; optional for port)
Pattern lifecycle + PG bridge:   Phase 7 (split with persistence track)
Omnimarket MCP bridge:           integration track (sponsor)
```

### Recommended start order (**port track** — agents, skills, nodes)

1. **Phase 2** — Agent coverage (`.cursor/agents` + `src/omnicursor/agents.py` tests)
2. **Phase 3 (Bucket 1)** — Skills + `compliance.py` + rules
3. **Phase 4** — ONEX nodes and `contract.yaml` under `src/omnicursor/nodes/`
4. **Phase 3 (Buckets 2–3)** — As dependencies and labeling allow

### Recommended start order (**hooks / integration / bus** — full repo)

1. **Phase 1** — Maintained (done); extend only for new hook needs (e.g. Phase 6 Linear injection)
2. **Phase 6** — Linear in hooks + rules, building on Phase 1 DoD/session JSON
3. **Phase 7** — Keep `learned_patterns.json` + loader; wire to team pattern store when ready; optional `OMNICURSOR_PATTERN_SYNC_HTTP` for dev
4. **Phase 5** — When the **team** commits to bus + consumers; align topics with omnimarket / infra (ONEX **node ports** in Phase 4 can proceed on the port track without waiting for Kafka)

---

## Key Constraints

- `omniclaude-main/` is **read-only reference** — never modify it
- Hook scripts must use **Python stdlib only** (no pip dependencies)
- `post-edit.py` / `on_edit.py` runs `ruff check` diagnostically — never `--fix`, never modifies files
- All Bucket 3 skills must be clearly labeled; do not silently simulate Linear/Kafka calls
- ONEX node invariants from `omnibase_core` apply: unidirectional flow `EFFECT → COMPUTE → REDUCER → ORCHESTRATOR`, nodes < 100 lines, all behavior declared in `contract.yaml`
- **Do not build capstone on** `onex run <contract.yaml>` until omnimarket routing validation is fixed upstream; use `python -m omnimarket.nodes.<node>` or in-process handlers
- **Do not** claim rules “block” tool calls — they guide; only the shell hook *denies*

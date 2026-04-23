# Cursor Feature Surface Map
## Every Cursor-native capability and how omniclaude logistics map onto it

**Purpose:** Reference for understanding every lever Cursor exposes and how each one replaces,
approximates, or supplements an omniclaude concept.

**Last updated:** 2026-04-21

---

## Cursor's Full Native Feature Surface

Cursor exposes seven distinct integration surfaces. OmniCursor currently uses two of them
(hooks + rules). The remaining five are either partially used or completely untapped.

| Surface | What it is | OmniCursor status |
|---|---|---|
| **Rules** | `.cursor/rules/*.mdc` — always-on or keyword-activated instructions injected into every prompt | Active (11 rules) |
| **Hooks** | `.cursor/hooks.json` — Python/shell scripts on 4 lifecycle events | Active (4 hooks) |
| **Agents** | `.cursor/agents/*.json` — background agent definitions | Config only (17 JSON files, no background execution wired) |
| **MCP Servers** | Model Context Protocol — tools the model can call, served via local HTTP or stdio | Configured (Linear MCP enabled in settings.json), not extended |
| **Notepads** | Named reusable context blocks, injected via `@notepad-name` in chat | Not used |
| **Settings** | `.cursor/settings.json` — IDE and model configuration | Minimal |
| **@-mentions** | `@file`, `@web`, `@docs`, `@codebase`, `@notepad` — context injection in chat | Not configured |

---

## Surface 1: Rules

**What Cursor does:** Before every AI response, Cursor evaluates all `.mdc` files in
`.cursor/rules/`. Files with `alwaysApply: true` inject their content into every prompt.
Files with `globs:` inject only when matching files are open. Files with `description:` inject
when the model decides they're relevant.

**omniclaude equivalent:** Always-on system prompt + skill SKILL.md injection via
`context_injection_wrapper.py`.

### Full mapping

| omniclaude concept | Cursor rules replacement |
|---|---|
| Always-on ONEX vocabulary | `00-omninode-concepts.mdc` (alwaysApply) |
| Codebase research discipline | `01-codebase-research.mdc` (alwaysApply) |
| Secret hygiene | `02-no-secrets-in-commits.mdc` (alwaysApply) |
| Skill methodology (brainstorming) | `10-brainstorming.mdc` (keyword-activated) |
| Skill methodology (plan writing) | `11-writing-plans.mdc` (keyword-activated) |
| Ticket pipeline methodology | `12-plan-ticket.mdc` (keyword-activated) |
| Debugging methodology | `13-systematic-debugging.mdc` (keyword-activated) |
| PR review methodology | `14-pr-review.mdc` (keyword-activated) |
| Handoff methodology | `15-handoff.mdc` (keyword-activated) |
| Linear ticket creation (Bucket 3) | `16-linear-create.mdc` (planned) |
| Linear ticket consumption (Bucket 3) | `17-linear-consume.mdc` (planned) |

### What rules cannot do

- Execute code (no subprocess, no Kafka, no HTTP)
- Read dynamic state (session state, learned patterns, ticket context)
- Block model behavior (no deny path — only guidance)

### Untapped rule capabilities

- **Glob-activated rules** — inject agent-specific instructions when the model opens matching
  files. Example: a rule that activates on `*.py` files and injects Python-specific ONEX coding
  standards. Currently all rules are keyword-activated or always-on.
- **Rules as slash commands** — by writing `description: "Activated when user types /skill-name"`,
  you create a lightweight slash command surface without any code. A rule with the full
  `SKILL.md` content becomes a self-contained command.

---

## Surface 2: Hooks

**What Cursor does:** On 4 lifecycle events, Cursor pipes JSON to a Python script via stdin and
reads the script's stdout JSON response.

**omniclaude equivalent:** Claude Code's 8-hook system.

### Current mapping

| Cursor hook | omniclaude equivalent | Coverage |
|---|---|---|
| `beforeSubmitPrompt` | UserPromptSubmit | Strong — agent routing + systemMessage injection |
| `beforeShellExecution` | PreToolUse(Bash) | Strong — HARD_BLOCK + SOFT_WARN guards |
| `afterFileEdit` | PostToolUse(Write/Edit) | Weak — diagnostic ruff only, no audit trail |
| `stop` | Stop + SessionEnd | Moderate — 4-gate outcome classification |

### Gaps (no Cursor equivalent)

| Missing omniclaude hook | Impact | Mitigation |
|---|---|---|
| `SessionStart` | No bootstrap — ticket context, session state init | First-prompt flag in `beforeSubmitPrompt`; write session state file on first call |
| `PreToolUse (non-shell)` | Cannot gate Edit/Write/Read tool calls | Encode constraints as always-on rules; trust the model to follow them |
| `PostToolUse (non-edit)` | Cannot audit after every tool | `afterFileEdit` partially covers; add session-level audit log in `stop` |
| `SubagentStart` | Cannot inject context into spawned agents | Background agent JSON configs are the replacement — inject once there |
| `PreCompact` | Cannot inject guidance before context compaction | Add compaction guidance to always-on rule `00-omninode-concepts.mdc` |

### Untapped hook capabilities

- **`afterFileEdit` as an audit trail** — currently only runs `ruff check`. Could append every
  edit event to `~/.omnicursor/events.jsonl` with file path, timestamp, and session ID,
  creating the equivalent of omniclaude's `post_tool_use_return_path_auditor.sh`.
- **`beforeSubmitPrompt` as SessionStart** — write a `~/.omnicursor/sessions/{id}.json` file
  on the first prompt of a session. All subsequent hooks can read this file for session context,
  implementing the SessionStart/SessionEnd lifecycle that Cursor doesn't natively expose.
- **`stop` as Kafka emitter** — on session end, `on_stop.py` can POST the session summary to
  the omniintelligence REST API directly (no Kafka needed for the write path).

---

## Surface 3: Background Agents

**What Cursor does:** Cursor can run agents autonomously in the background using agent
definition JSON files in `.cursor/agents/`. Each agent has a name, description, system prompt,
and capability set. The user can invoke a background agent by name or Cursor can route to one
automatically.

**omniclaude equivalent:** `claude -p` headless execution + `node_delegation_orchestrator` +
`node_skill_*_orchestrator` nodes.

### Full mapping

| omniclaude concept | Cursor background agent replacement |
|---|---|
| `claude -p "Run ticket-pipeline for OMN-1234"` | Background agent `ticket-pipeline` invoked by name |
| Agent YAML with `trigger_phrases` | Agent JSON `activation_patterns` + `explicit_triggers` |
| `node_skill_merge_sweep_orchestrator` | Background agent `merge-sweep` with merge-sweep skill instructions |
| `node_delegation_orchestrator` | `polymorphic-agent` background agent — general-purpose delegation |
| Subagent spawning via `Task` tool | Cursor's agent-to-agent delegation (if supported) |

### What's already in place

17 agent JSON configs exist in `.cursor/agents/`. These define the agent pool but are currently
only used by the routing hook (`on_prompt.py`). To make them actually execute as background
agents, each needs a `system_prompt` field with the full skill methodology plus ONEX constraints.

### What background agents could add later (optional)

OmniCursor’s **foundation** uses the same JSON for **routing** (`beforeSubmitPrompt`). Turning configs into **executing** background agents is **optional** and product-version-dependent:

1. **Ticket-style workflows** — a dedicated background agent could read Linear context and run a skill methodology.
2. **Automation** — scheduled or recurring runs for merge/CI-style workflows **if** you add agents for that purpose.
3. **Delegation** — `polymorphic-agent` or new JSON agents only when you choose to model them.

### Gap

Background agent invocation API and exact JSON schema may vary by Cursor version. The
`.cursor/agents/*.json` format should be treated as a capability gate, not a guarantee.

---

## Surface 4: MCP Servers (the key unlock)

**What Cursor does:** Cursor supports Model Context Protocol servers. An MCP server exposes
tools that the model can call during a conversation. Cursor connects to MCP servers defined in
`.cursor/mcp.json` or via `settings.json`.

**omniclaude equivalent:** Kafka topics + omniintelligence REST API + omnimemory + Linear MCP.

**Sponsor direction (2026-04-16):** First **omnimarket** MCP-backed bridge (`uv run python -m omnimarket.nodes.<node>` or in-process handlers) is an **integration** priority — **separate** from the **port track** ([MIGRATION_PHASES_HANDOFF.md](./MIGRATION_PHASES_HANDOFF.md)) unless explicitly in scope. See [SPONSOR_ALIGNMENT_2026-04-16.md](./SPONSOR_ALIGNMENT_2026-04-16.md).

### Why MCP is the most important untapped surface

omniclaude's external integrations (Kafka, omniintelligence, omnimemory, Linear) all require
the model to call external services. In Claude Code this happens via the emit daemon and hook
scripts. In Cursor, **MCP servers are the only way to give the model direct tool access to
external services**.

### Full mapping

| omniclaude integration | MCP server replacement |
|---|---|
| **Portable ONEX nodes (review, polish, pipelines)** | **Omnimarket subprocess or in-process** — sponsor capstone **integration** bridge |
| Linear ticket pipeline (`ticket_context_injector.py`) | Linear MCP (already enabled in settings.json) |
| Kafka emit daemon (`emit_client_wrapper.py`) | Custom MCP server: `onex-events` — long-term / full stack |
| omniintelligence REST API (pattern injection) | Optional MCP or **local / PG** pattern store; direct service APIs **not** capstone default |
| omnimemory (Qdrant/Memgraph) | Custom MCP server: `omnimemory` — exposes `search_memory`, `store_memory` |
| omnidash event stream | Custom MCP server: `omnidash` — exposes `get_session_events` |

### Proposed MCP servers

#### `omnimarket-bridge` MCP server (sponsor integration priority)

Thin wrapper that runs vetted omnimarket nodes (e.g. `node_local_review`) via **Path B** (`python -m`) or **Path C** (handler import). **Not** part of this repo’s default checklist — design reference for coordination.

#### `onex-events` MCP server
Wraps Kafka publish so the model can emit ONEX events directly:
```json
tools:
  - emit_hook_event(event_type, session_id, payload) → ack
  - get_session_events(session_id) → events[]
```
Implements the same wire protocol as omniclaude's Unix socket emit daemon, but over MCP instead.

#### `omniintelligence` MCP server
Bridges the omniintelligence REST API:
```json
tools:
  - get_patterns(domain, limit) → patterns[]
  - store_pattern(pattern_id, description, domain, confidence) → ack
  - classify_intent(prompt) → intent_class, confidence
```
Replaces `context_injection_wrapper.py` — the model can call `get_patterns` directly instead
of having the hook inject them passively.

#### `omnimemory` MCP server
Exposes Qdrant semantic search:
```json
tools:
  - search_memory(query, limit) → results[]
  - store_memory(key, content, metadata) → ack
```

### MCP configuration

Add to `.cursor/settings.json`:
```json
{
  "mcpServers": {
    "linear": { "enabled": true },
    "onex-events": {
      "command": "python3",
      "args": ["-m", "omnicursor.mcp.events_server"],
      "env": { "KAFKA_BOOTSTRAP": "localhost:9092" }
    },
    "omniintelligence": {
      "command": "python3",
      "args": ["-m", "omnicursor.mcp.intelligence_server"],
      "env": { "OMNIINTELLIGENCE_URL": "http://localhost:8053" }
    }
  }
}
```

---

## Surface 5: Notepads

**What Cursor does:** Notepads are named reusable context blocks stored in the IDE. A user
types `@notepad-name` in the chat to inject the notepad content into the current prompt.

**omniclaude equivalent:** `skills/*.md` files + the `@file` skill loading pattern.

### Mapping

| omniclaude concept | Cursor notepad replacement |
|---|---|
| `SKILL.md` files loaded by agent on demand | Notepads stored per skill — user types `@brainstorming` to inject |
| Context injection payload from hooks | A `@onex-context` notepad with ONEX vocabulary + session state |
| Ticket context block | A `@ticket-context` notepad refreshed at session start |

### What notepads add that rules can't

Rules inject passively and unconditionally. Notepads inject **on demand** when the user or
agent explicitly references them. This makes notepads better for:
- Skills with large content (the model only reads them when invoked)
- Dynamic context (notepad content can be updated by a hook or script)
- User-visible skill library (the user sees what's available and chooses)

### Gap

Notepads are currently only writable through the Cursor IDE UI. There is no API to write a
notepad from a hook script. This limits dynamic injection — a hook can't update a notepad with
fresh ticket context. Workaround: write to a file and have a rule reference `@file` instead.

---

## Surface 6: Settings

**What Cursor does:** `.cursor/settings.json` configures the IDE, model selection, MCP server
list, and feature flags.

**omniclaude equivalent:** `.env.example` + `hooks/config.yaml` + `model_router_hook.yaml`.

### Full configuration surface

```json
{
  "mcpServers": { ... },          // MCP server registry
  "plugins": { ... },             // Plugin feature flags
  "model": "claude-sonnet-4-6",  // Default model
  "rules": {
    "alwaysInclude": ["..."]      // Force-include specific rules
  },
  "agent": {
    "maxTokens": 32000,           // Token budget per turn
    "tools": ["read", "edit", "terminal", "mcp"]  // Allowed tool types
  }
}
```

### omniclaude config items to port

| omniclaude config | Settings.json equivalent |
|---|---|
| `ONEX_MODEL=claude-sonnet-4-6` | `"model": "claude-sonnet-4-6"` |
| `USE_LLM_ROUTING=true` | Add `omniintelligence` MCP server |
| `HARD_FLOOR=0.55` | Hook config only (not a settings.json concern) |
| Linear MCP enabled | `"mcpServers": {"linear": {"enabled": true}}` |
| Allowed tool surface | `"agent": {"tools": [...]}` |

---

## Surface 7: @-mentions

**What Cursor does:** In chat, users can type `@file`, `@docs`, `@web`, `@codebase`,
`@notepad`, `@definition` to inject context into the prompt.

**omniclaude equivalent:** The `Read` tool + `additionalContext` hook injection.

### Mapping for omniclaude workflows

| omniclaude context source | @-mention equivalent |
|---|---|
| Ticket metadata from Linear | `@linear-ticket OMN-1234` (via Linear MCP) |
| Learned patterns from omniintelligence | `@notepad onex-patterns` or `@omniintelligence get_patterns` (via MCP) |
| Skill SKILL.md content | `@file skills/systematic-debugging.md` |
| Architecture docs | `@file docs/ARCHITECTURE.md` |
| Web search for context | `@web "cursor hooks API"` |

---

## Summary: omniclaude → Cursor capability map

| omniclaude concept | Primary Cursor surface | Secondary Cursor surface | Gap? |
|---|---|---|---|
| Always-on system prompt | Rules (alwaysApply) | — | No |
| Agent routing | Hooks (beforeSubmitPrompt) | Agents (JSON configs) | No |
| Skills as slash commands | Rules (keyword-activated) | Notepads (@mention) | Partial — no native /cmd registry |
| Context injection (patterns) | Hooks (systemMessage) | MCP (omniintelligence) | No |
| Ticket context injection | Hooks (first-prompt) | MCP (Linear) | No |
| Kafka event emission | MCP (onex-events) | Hooks (stop → REST) | Not built yet |
| PreToolUse (all tools) | Rules (constraints) | — | **Yes — no hook** |
| PreToolUse (shell only) | Hooks (beforeShellExecution) | — | No |
| PostToolUse (edits) | Hooks (afterFileEdit) | — | Partial |
| SessionStart | Hooks (first-prompt flag) | — | Partial |
| SessionEnd | Hooks (stop) | — | No |
| SubagentStart context | Agents (system_prompt field) | — | Partial |
| PreCompact guidance | Rules (alwaysApply) | — | Partial |
| Headless automation | Background Agents | — | Not wired yet |
| omniintelligence patterns | Local / PG + file (capstone) | MCP (optional) / Hooks (`OMNICURSOR_PATTERN_SYNC_HTTP`) | Partial |
| omnimemory storage | MCP (omnimemory) | — | Not built yet |
| DoD enforcement | Hooks (beforeShellExecution) | Rules | Partial |
| Dispatch claim guard | Hooks (beforeShellExecution) | Rules | Partial |

---

## Recommended build order — port track (agents, skills, ONEX nodes & contracts)

Aligned with [MIGRATION_PHASES_HANDOFF.md](./MIGRATION_PHASES_HANDOFF.md) — **foundation first**, omniclaude as **reference only**:

1. **Agents** — keep the **current JSON set** healthy; add agents **only when a workflow needs them**; keep `src/omnicursor/agents.py` and routing tests aligned.
2. **Skills** — keep shipped `skills/*.md` + `compliance.py` + rules consistent; add skills **sparingly** (on the order of **~12–17 curated** skills unless scope widens).
3. **ONEX nodes** — harden `src/omnicursor/nodes/*` (`contract.yaml`, handlers, tests) **when** a demo or integration needs it; pattern **writes** and bus **emit** stay other tracks unless assigned.

Optional later: **background agent `system_prompt`** fields if Cursor execution model is confirmed for your version.

## Recommended build order — hooks / observability / integration (full repo)

1. **Wire background agents** — add `system_prompt` fields to existing agent JSON files so
   they actually execute as background agents, not just routing metadata.
2. **Expand `afterFileEdit`** — write full audit events to `~/.omnicursor/events.jsonl`, not
   just ruff diagnostics. Gives PostToolUse-level observability.
3. **Hooks + `learned_patterns.json`** — keep prompt-time pattern injection solid; use `OMNICURSOR_PATTERN_SYNC_HTTP` only for dev pulls; authoritative **PG / store_pattern** lives with the team’s persistence track.
4. **Phase 6-style hook work** — Linear ticket sniffing + `systemMessage`, DoD session fields (as in migration plan).
5. **Optional MCP** — only if this repo’s scope explicitly includes a new server; omnimarket bridge is a **separate** integration track per sponsor.
6. **Add `onex-events` MCP server** — long-term / full stack; only if assigned to this codebase.
7. **Notepads for skills** — when Cursor exposes a notepad write API, migrate top 12 skills
   from `skills/*.md` to notepads for @-mention access.

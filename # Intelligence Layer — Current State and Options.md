# Intelligence Layer — Current State and Options

## Current State

The intelligence layer has three pieces at different stages of completion.

### What works today (no infrastructure required)

Local pattern learning runs end-to-end:

```
stop hook → pattern_writer.py → ~/.omnicursor/learned_patterns.json
user-prompt-submit hook → pattern_loader.py → injects patterns into system message
```

Each session end updates `learned_patterns.json`:

- **Metrics on every outcome** (success / failed / abandoned / unknown):
  `injection_count` is incremented for each known `injected_pattern_id` from
  the session's `prompt_classified` events.
- **Learning gated by success + edits**: new patterns are extracted from
  `prompt_snippet` and upserted **only** when `session_outcome == "success"`
  **and** `files_edited > 0`. Weight is decayed by age; total records are
  capped at 20 per domain via `_evict_overflow`; low-utilization records are
  removed by `_evict_low_utilization` after enough injections.
- **Read path unchanged**: the user-prompt-submit hook still loads
  `~/.omnicursor/learned_patterns.json` and injects the top 5 most relevant
  patterns into the next prompt. This works with zero infrastructure.

**Status:** Gap closed by Option A (2026-05-10). Each pattern record now tracks
`injection_count` and `utilization_successes`; the weight update applies a 1.5×
multiplier on success after a real injection, and patterns whose utilization rate
stays below threshold after enough injections are evicted.

**Caveat:** the utilization signal is still a **proxy** — it correlates session
success with prior injection. It is **not** an LLM-based confirmation that
Claude actually read or applied the injected pattern text. That stronger
confirmation is **out of scope for Option A** and is not delivered by this
work. For the current demo and roadmap, the **next step is Option B** — wire
OmniCursor's session outcomes into omniintelligence over HTTP.

### What is stubbed but not wired

`emit_client.py` sends events to a Unix socket (`~/.omnicursor/emit.sock`). The
stop hook calls `send_event("onex.evt.omnicursor.session-ended.v1", ...)` after
every session. But nothing is listening on that socket — it is never created. All
events are silently dropped.

### What is opt-in and incomplete

`pattern_sync.py` can GET patterns from an HTTP endpoint and overwrite the local
JSON file. The stop hook calls it when `OMNICURSOR_PATTERN_SYNC_HTTP=1`. Two
problems:

1. The hardcoded default URL (`http://127.0.0.1:8053`) does not match what the
   compose stack exposes (intelligence-reducer is on port 18091).
2. This is a **read-only sync** — patterns are pulled from omniintelligence but
   never written to it. OmniCursor has no path to push session outcomes or
   utilization signals upstream.

### What the compose stack provides

Julian's `compose.yaml` starts the full omniintelligence pipeline:

- **Postgres** — pattern storage, session outcome DB
- **Redpanda** — Kafka-compatible event bus
- **Valkey** — session state cache
- **intelligence-reducer** (port 18091) — processes Kafka events, writes to Postgres
- **intelligence-orchestrator** (port 18092) — coordinates workflows
- **quality-scoring-compute** (port 18093) — utilization scoring node

The infrastructure is ready to receive and process events. It is not connected to
OmniCursor yet.

---

## Options

### Option A — Extend local learning (no infrastructure)

**Status: Complete — verified 2026-05-10.** Implemented end-to-end, stdlib only,
no infrastructure dependency. Verification: `ruff check` clean, `pytest -q` 572
passed (1.05s) on rama `julian/option-b-from-main`.

Improve the existing flat-file system to add a utilization proxy signal without
any external dependencies.

**What changed (delivered):**
- Each record in `learned_patterns.json` carries `injection_count` and
  `utilization_successes`, plus a deterministic `pattern_id` (`auto-` +
  `sha1(domain:pattern_key)[:12]`, with legacy backfill on load).
- `user-prompt-submit.py` emits `injected_pattern_ids` on every
  `prompt_classified` event (alongside the existing `patterns_injected` count).
- `stop.py` calls `write_session_patterns(..., session_outcome)` for **any**
  outcome (success / failed / abandoned / unknown), not only success.
- `pattern_writer.py`:
  - Any outcome: `injection_count += 1` per known injected ID (deduplicated
    within an event; unknown IDs skipped silently).
  - `success` only: `utilization_successes += 1` and `weight` gets
    `WEIGHT_INCREMENT × 1.5` (`UTILIZATION_SUCCESS_WEIGHT_MULTIPLIER`).
  - `_evict_low_utilization` removes records once `injection_count` exceeds
    `UTILIZATION_EVICT_MIN_INJECTIONS` (10) and the success rate stays below
    threshold; `_evict_overflow` caps at 20 records per domain.
  - `_save_patterns` writes atomically via `tempfile.mkstemp` + `os.replace`.
- No new services, no new dependencies, stdlib only throughout.

**Tradeoffs:**
- Zero infrastructure friction — works offline, always
- Utilization signal is a proxy: session success ≠ pattern was used
- No LLM-based check of whether Claude actually read the pattern text
- JSON file schema gets richer — concurrent write risk remains (mitigated by
  atomic rename already in place)
- Does not integrate with omniintelligence or OmniDash

**Effort:** low (~50–80 lines across `pattern_writer.py` and `stop.py`)

---

### Option B — Local-first bridge (no live upstream required)

**Status: Complete — verified 2026-05-09.** Implemented as "B mínima": a
local-first bridge that prepares OmniCursor to hand data to Option C without
depending on a running `intelligence-reducer`. The original design assumed a
working HTTP write path to the reducer; audit found the reducer runs in stub mode
(only `/health`) and exposes no `POST` endpoint for session outcomes. B mínima
delivers the contract and fallbacks without pretending those endpoints exist.

**What changed (delivered):**
- `pattern_sync` ported to a **defensive read path**: probes `/health` before
  fetching `/api/v1/patterns`; returns False without touching the local JSON file
  if the service is offline, in stub mode, or returns an unexpected body. Default
  URL updated to `http://127.0.0.1:18091`. Atomic write via `tempfile.mkstemp` +
  `os.replace`. `OMNIINTELLIGENCE_URL` env var overrides the default.
- **Durable outbox** (`~/.omnicursor/outbox.jsonl`): `stop.py` appends one JSON
  line per session (any outcome) using schema `omnicursor.session_outcome.v1`.
  Payload includes `injected_pattern_ids` (deduplicated), `matched_agent`,
  `patterns_injected`, and `ended_at` (ISO 8601 UTC with Z). The outbox is the
  contract-frozen payload that **Option C** will drain to Kafka / OmniIntelligence
  when ready.
- **MCP/Omnimarket bridge restored**: `omnimarket/` checkout at
  `ce0f3bec8a049bb9ae728adee2d053fd4cebe28b` (branch `main`). `.cursor/mcp.json`
  points there; `run_local_review(dry_run=True)` returns `ok: true`. Enables demo
  scenario "hooks disabled → MCP-only fallback". `.gitignore` excludes `omnimarket/`.
- **Local JSON remains the read cache**: pattern_loader.py continues to read
  `~/.omnicursor/learned_patterns.json` unchanged. Option A and the local file are
  authoritative; the write path to omniintelligence comes in Option C.

**What B deliberately does NOT deliver:**
- POST to `intelligence-reducer` — no endpoint exists. Deferred to C.
- Kafka producer / Redpanda integration — deferred to C.
- Namespace alignment (`onex.evt.omnicursor.*` ↔ `onex.evt.omniclaude.*`) — deferred to C.
- Translation of `auto-<sha1>` pattern IDs to upstream UUIDs — deferred to C.
- OmniDash integration — deferred to C.
- Outbox rotation / drain — C will drain the JSONL to Kafka; B just appends.

**Tradeoffs:**
- Zero infrastructure friction — works offline, always (same as Option A)
- No real-time feedback from omniintelligence — outbox accumulates locally
- HTTP read path (`OMNICURSOR_PATTERN_SYNC_HTTP=1`) degrades gracefully if stack
  is offline or stub, but provides no new intelligence until Option C lands
- Outbox grows without rotation (by design in B mínima — C drains it)

**Effort delivered:** low (~150 lines across `pattern_sync.py`, `stop.py`, and
new `session_outbox.py`)

---

### Option C — Emit to Kafka and let omniintelligence process natively

Change the emit client to write events to Redpanda instead of the Unix socket.
omniintelligence processes `utilization.scoring.requested` events from Kafka
identically to how it handles OmniClaude events — OmniCursor just becomes
another event producer.

**What changes:**
- Replace the Unix socket emit client with a Kafka producer (requires a Kafka
  client library — breaks the stdlib-only hook constraint unless moved to a
  sidecar process)
- Align event namespace to `onex.evt.omniclaude.*` or register a new
  `onex.evt.omnicursor.*` consumer in omniintelligence
- Stop hook emits `utilization.scoring.requested` with `injected_pattern_ids`
  and `session_outcome`
- Pattern reads come from intelligence-reducer HTTP endpoint (same as Option B)

**What this enables:**
- Full OmniClaude-equivalent intelligence loop
- LLM-based utilization scoring via quality-scoring-compute
- OmniDash shows OmniCursor sessions natively
- Pattern state machine runs identically for both IDEs

**Tradeoffs:**
- Kafka client (`confluent-kafka` or `kafka-python`) is a pip dependency —
  hooks cannot use it directly; requires a sidecar daemon or moving event
  emission out of the hook process
- Hard dependency on compose stack; no offline fallback for the write path
- Namespace alignment may require changes to omniintelligence consumers
  (upstream work outside OmniCursor)

**Effort:** high (sidecar daemon, Kafka producer, namespace alignment, upstream
consumer registration)

---

## Recommended Path

**Option A and B are done. Next: Option C.**

1. **Option A — done (2026-05-10).** Closes the utilization gap with no
   infrastructure dependency and ships a real (proxy) feedback signal.
2. **Option B — done (2026-05-09).** Local-first bridge: defensive pattern_sync,
   durable outbox (`omnicursor.session_outcome.v1`), and MCP/Omnimarket fallback
   functional. No live upstream required.
3. **Option C — next / long-term.** Wire the outbox to Kafka (`omnibase_infra` /
   Redpanda), align namespace to `onex.evt.omniclaude.*` or register a new
   consumer in `omniintelligence`, enable quality-scoring-compute for LLM-based
   utilization scoring, and surface patterns in OmniDash. Requires a sidecar
   architecture decision for the Kafka producer (hooks must stay stdlib-only).
   Treat as the next integration milestone after the current demo.

The key design constraint across all options: **the local JSON file is always
the read cache**. Whether patterns come from `pattern_writer.py` (Option A) or
intelligence-reducer HTTP (Options B/C), the user-prompt-submit hook always reads
from `~/.omnicursor/learned_patterns.json`. This keeps the hook stdlib-only and
makes the stack optional rather than required.

---

## Current Wiring Gaps (regardless of option chosen)

| Gap | File | Fix |
|-----|------|-----|
| Emit socket never created — all events dropped | `emit_client.py` | Create socket listener or replace with HTTP |
| `pattern_sync.py` port wrong (8053 vs 18091) | `pattern_sync.py` | Update default URL to match compose stack |
| No write path to omniintelligence | `stop.py`, `pattern_sync.py` | Add POST after session end |
| `OMNICURSOR_PATTERN_SYNC_HTTP` not in `.env.omninode.example` | `.env.omninode.example` | Document the toggle |
| Namespace mismatch (`omnicursor.*` vs `omniclaude.*`) | `emit_client.py`, `stop.py` | Align or register new consumer |

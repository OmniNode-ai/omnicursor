# Option C vs Main — What Changed

This document compares the `intelligence/option-c` branch against `main`.
Option C is a superset of main — everything in main works exactly the same,
and Option C adds the event pipeline on top.

**Summary:** 60 files changed, 7,451 lines added, 158 lines modified.

---

## New modules (do not exist in main)

### `src/omnicursor/sidecar/`

The sidecar daemon — runs alongside Cursor and connects it to the event bus.

| File | What it does |
|---|---|
| `socket_listener.py` | Binds `~/.omnicursor/emit.sock`, receives events from hooks, appends to outbox |
| `daemon.py` | CLI entry point — runs socket listener + drain loop together, handles SIGTERM/SIGINT cleanly |

Start it with: `bash scripts/run_sidecar.sh --publisher noop|kafka`

### `src/omnicursor/drainer/`

Reads the outbox and publishes events to a backend.

| File | What it does |
|---|---|
| `loop.py` | Polls outbox every N seconds, calls publisher for each new row |
| `publisher.py` | Abstract publisher interface + `NoopPublisher` (logs only, no side effects) |
| `kafka_publisher.py` | Produces events to Redpanda/Kafka topics with multi-topic fan-out |
| `omnidash_publisher.py` | Writes fixture files for OmniDash (local demo without Kafka) |
| `omnidash_bridge.py` | Bridge between outbox schema and OmniDash fixture format |
| `reader.py` | Reads new lines from outbox.jsonl from a cursor offset |
| `cursor.py` | Reads/writes the drain cursor file (tracks how far through outbox we've read) |
| `transform.py` | Converts outbox rows into typed events for the publisher |

### `src/omnicursor/session_outbox.py`

Writes one structured JSON record to `~/.omnicursor/outbox.jsonl` at session end.
Schema: `omnicursor.session_outcome.v1` — includes session outcome, agent matched,
confidence, files edited, patterns injected, timestamps.

### `config/event_registry/omnicursor.yaml`

Registers the `omnicursor` namespace in the omniintelligence topic registry.
Maps event types to Kafka topics:

| Event type | Kafka topics |
|---|---|
| `session.outcome` | `onex.cmd.omniintelligence.session-outcome.v1`, `onex.evt.omnicursor.session-outcome.v1` |
| `utilization.scoring.requested` | `onex.cmd.omniintelligence.utilization-scoring.v1` |
| `prompt.submitted` | `onex.evt.omnicursor.prompt-submitted.v1` |

### `scripts/run_sidecar.sh`

One-command sidecar launcher. Resolves the venv from the parent repo if running
from a worktree.

```bash
bash scripts/run_sidecar.sh --publisher noop    # testing
bash scripts/run_sidecar.sh --publisher kafka   # production
```

### `scripts/smoke_test.py`

Fires a test `session.outcome` event at the socket and prints the response.
Used to verify the socket → outbox → drain pipe is live before a demo.

### `scripts/watch_outbox.py`

Colorized real-time monitor for `~/.omnicursor/outbox.jsonl`. Shows each entry
formatted with color-coded outcome (green=success, red=failed, yellow=abandoned),
agent name, confidence, files edited, and patterns injected.

---

## Modified files (exist in main, changed in option-c)

### `.cursor/hooks/scripts/stop.py`

**In main:** classifies session outcome, writes patterns, logs event.

**Added in option-c:**
- Builds a structured outbox payload aggregating all `prompt_classified` events
  from the session (agent, confidence, files edited, injected pattern IDs)
- Calls `write_session_outcome()` → writes to `outbox.jsonl`
- Calls `send_event("session.outcome", ...)` → emits to Unix socket
- Calls `send_event("utilization.scoring.requested", ...)` → emits utilization event

### `.cursor/hooks/scripts/user-prompt-submit.py`

**In main:** loads patterns from local file cache only.

**Added in option-c:**
- On every prompt, attempts `GET /api/v1/patterns?domain=X` on the
  omniintelligence HTTP API (`INTELLIGENCE_SERVICE_URL`, default `localhost:8053`,
  900ms timeout)
- Uses API response as the pattern source if available
- Falls back to local file cache transparently if API is down or times out

This matches OmniClaude's per-prompt context injection behavior.

### `src/omnicursor/pattern_writer.py`

**In main:** writes learned patterns on successful sessions, basic weight mechanics.

**Added in option-c:**
- `pattern_id` field — deterministic hash (`auto-<sha1[:12]>`) per domain+keyword
- Tracks `injection_count` and `utilization_successes` per pattern
- Updates injection metrics on any session outcome (not just success)
- Evicts patterns with low utilization rate (injected often, rarely successful)
- Atomic writes via `tempfile.mkstemp` + `os.replace` (safer than `.tmp` rename)
- `write_session_patterns()` now accepts `session_outcome` parameter

### `src/omnicursor/sync/pattern_sync.py`

**In main:** basic HTTP sync stub.

**Added in option-c:**
- Health probe before attempting sync (`_probe_health()`)
- Merge-local-priority: local patterns always win, remote appended only if absent
- Strict body validation — returns `False` (not empty list) on unexpected format
- Atomic writes via `tempfile.mkstemp`
- Uses `_base_url()` helper for configurable endpoint

### `.cursor/hooks/lib/emit_client.py`

**In main:** minimal stub.

**Added in option-c:** Full Unix socket client with ping support, retry logic,
configurable socket path, and `send_event()` function used by stop hook.

---

## Test coverage comparison

| Test file | Main | Option C | What's new |
|---|---|---|---|
| `test_suite_event4_stop.py` | 51 tests | 66 tests | +15 outbox + socket emit tests |
| `test_suite_event1_prompt.py` | — | 142 tests | Full new suite for prompt hook |
| `test_pattern_writer.py` | baseline | 41 tests | pattern_id, injection tracking, utilization eviction |
| `test_drainer.py` | — | 37 tests | Full drainer module coverage |
| `test_emit_client.py` | baseline | 19 tests | Socket client, ping, retry |
| `test_omnidash_publisher.py` | — | 18 tests | OmniDash fixture writer |
| `test_sidecar.py` | — | 13 tests | KafkaPublisher, socket listener, drain loop stop |
| `test_session_outbox.py` | — | 11 tests | Outbox schema, append, dedup |
| `test_pattern_sync.py` | — | 14 tests | Health probe, merge-local-priority, strict validation |

**Total tests — main: ~500 | option-c: 691**

---

## What option-c does NOT change

Everything else in main is untouched:

- Agent routing logic and all 18 agent configs
- All 16 skills
- Shell guard rules
- Post-edit hook
- Node contracts (5 nodes)
- Scoring engine
- MCP bridge
- Docker Compose stack
- CI/CD workflows
- All existing passing tests

---

## The full data flow (option-c only)

```
User submits prompt
  └─► user-prompt-submit.py
        ├─► GET /api/v1/patterns (omniintelligence, 900ms timeout)
        │     └─► fallback: local learned_patterns.json
        └─► inject patterns + agent persona into system message

Session ends
  └─► stop.py
        ├─► write_session_outcome() → ~/.omnicursor/outbox.jsonl
        ├─► send_event("session.outcome") → ~/.omnicursor/emit.sock
        └─► send_event("utilization.scoring.requested") → socket

Sidecar (run_sidecar.sh, always running)
  ├─► socket_listener: receives live events, appends to outbox
  └─► drain_loop (2s tick): reads outbox → KafkaPublisher
        └─► Redpanda → omniintelligence
              └─► pattern weights updated
                    └─► injected at next prompt  ◄── loop closes here
```

---

## How to run option-c

```bash
# One-time setup
source /home/andyw/cs490/omninode/OmniCursor/.venv/bin/activate
cd /home/andyw/cs490/omninode/OmniCursor/.worktrees/intelligence-option-c
pip install -e ".[dev]"

# Run tests
pytest tests/ -q                          # 691 tests
pytest tests/test_sidecar.py -v           # sidecar unit tests only

# Run the sidecar
bash scripts/run_sidecar.sh --publisher noop

# Smoke test (sidecar must be running)
python3 scripts/smoke_test.py

# Watch events in real time
python3 scripts/watch_outbox.py
```

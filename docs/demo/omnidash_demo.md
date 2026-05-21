# OmniDash Live Event Stream — Demo Runbook

## What this proves

End-to-end flow without Kafka:

```
Cursor stop hook
  → ~/.omnicursor/outbox.jsonl          (durable outbox row)
  → drainer (drain_loop, 2-second tick)
  → OmniDashFixturePublisher
  → /tmp/omnicursor-omnidash-fixtures/
      onex.snapshot.projection.live-events.v1/
        index.json  ← list of event files
        0.json, 1.json, …  ← LiveEvent rows
  → OmniDash Express bridge
      GET /projection/onex.snapshot.projection.live-events.v1
  → OmniDash Vite SPA
      Live Event Stream widget
```

## What this does NOT prove

- Real Kafka bus or omniintelligence consumer.
- Real LLM-based utilization scoring (scoring is deferred post-demo).
- Production OmniDash deployment (this runs dev servers locally).
- KafkaPublisher or service-mode sidecar daemon (deferred post-demo).

---

## Three-terminal setup

### Terminal 1 — Express bridge (file mode, port 3002)

```bash
cd /path/to/omnidash
OMNIDASH_DATA_SOURCE=file \
FIXTURES_DIR=/tmp/omnicursor-omnidash-fixtures \
npm run dev:server
```

The `OMNIDASH_DATA_SOURCE=file` override is required — the contract.yaml default
is `sqlite`, which ignores `FIXTURES_DIR`.

### Terminal 2 — Vite SPA (HTTP data source, points to port 3002)

```bash
cd /path/to/omnidash
VITE_DATA_SOURCE=http \
VITE_HTTP_DATA_SOURCE_URL=http://localhost:3002 \
npm run dev
```

Open the URL printed by Vite (typically http://localhost:5173).
Navigate to the Live Event Stream widget.

### Terminal 3 — OmniCursor bridge (drains every 2 seconds)

```bash
cd /path/to/OmniCursor
bash scripts/run_omnidash_bridge.sh
```

Optional env overrides:
```bash
OMNIDASH_FIXTURES_DIR=/tmp/my-fixtures \
OMNICURSOR_BRIDGE_INTERVAL=1 \
bash scripts/run_omnidash_bridge.sh
```

---

## Generating events

End a Cursor session naturally (close the composer or wait for the stop hook).
`stop.py` appends a row to `~/.omnicursor/outbox.jsonl`; the bridge picks it up
within the next poll interval and writes fixture files.

### Manual smoke (no OmniDash required)

```bash
echo '{"schema_version":"omnicursor.session_outcome.v1","source":"omnicursor","conversation_id":"smoke-1","correlation_id":"corr-1","session_outcome":"success","session_outcome_reason":"smoke","files_edited":1,"matched_agent":"debugging","matched_confidence":0.9,"started_at":"2026-05-11T10:00:00Z","ended_at":"2026-05-11T10:00:05Z","injected_pattern_ids":["auto-x"]}' \
  > /tmp/smoke-outbox.jsonl

.venv/bin/python -m omnicursor.drainer.omnidash_bridge \
  --outbox /tmp/smoke-outbox.jsonl \
  --cursor /tmp/smoke.cursor \
  --fixtures /tmp/omnicursor-omnidash-fixtures \
  --once

cat /tmp/omnicursor-omnidash-fixtures/onex.snapshot.projection.live-events.v1/index.json
cat /tmp/omnicursor-omnidash-fixtures/onex.snapshot.projection.live-events.v1/0.json \
  | python -m json.tool
```

Expected: `index.json` is `["0.json","1.json"]` (session.outcome + utilization
because `injected_pattern_ids` is non-empty); `0.json` is a valid LiveEvent row.

---

## Stopping

- Terminal 3: `Ctrl+C` or `kill <PID>` — exits cleanly (SIGTERM → KeyboardInterrupt).
- Fixtures persist in `/tmp/omnicursor-omnidash-fixtures/` between runs.
  Delete the directory to reset the widget to an empty state.

---

## Key env vars reference

| Variable | Consumer | Effect |
|---|---|---|
| `OMNIDASH_DATA_SOURCE=file` | Express server | Reads projections from `FIXTURES_DIR` instead of sqlite |
| `FIXTURES_DIR` | Express server | Root fixtures directory served by the bridge |
| `VITE_DATA_SOURCE=http` | Vite SPA | Fetches projections via HTTP instead of bundled fixtures |
| `VITE_HTTP_DATA_SOURCE_URL` | Vite SPA | Base URL of the Express server (e.g. `http://localhost:3002`) |
| `OMNIDASH_FIXTURES_DIR` | `run_omnidash_bridge.sh` | Root fixtures dir written by the bridge (default: `/tmp/omnicursor-omnidash-fixtures`) |
| `OMNICURSOR_BRIDGE_INTERVAL` | bridge script / `--interval` | Seconds between drain passes (default: 2) |
| `OMNICURSOR_OUTBOX_FILE` | bridge script | Path to outbox.jsonl (default: `~/.omnicursor/outbox.jsonl`) |
| `OMNICURSOR_BRIDGE_CURSOR` | bridge script | Path to bridge cursor file (default: `~/.omnicursor/omnidash.cursor`) |

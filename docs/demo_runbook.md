# OmniCursor Demo Runbook

Two-act demo. Total time: ~15 minutes.

- **Act 1** — Ticket-to-code pipeline: type a task description, OmniCursor creates
  a Linear ticket, implements the code autonomously, and opens a PR.
- **Act 2** — Option C observability: the session from Act 1 appears as a live event
  in OmniDash within 2 seconds, sourced from the Unix socket sidecar.

Commands below use `$OMNICURSOR_ROOT` for the OmniCursor repo and `$OMNIDASH_ROOT`
for the OmniDash repo. Set these once before starting:

```bash
export OMNICURSOR_ROOT=<absolute path to OmniCursor repo>
export OMNIDASH_ROOT=<absolute path to OmniDash repo>
```

---

## Prerequisites

These only need to be done once.

### 1. Python venv

```bash
cd "$OMNICURSOR_ROOT"
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Linear MCP

Verify Linear MCP is configured in `~/.cursor/mcp.json`. It should contain a
`linear` entry. If not, follow `QUICKSTART.md`.

Quick check — open Cursor and run:
```
/plan-ticket test
```
If it calls `tracker.list_teams` without erroring, Linear MCP is live.

### 3. OmniDash dependencies

```bash
cd "$OMNIDASH_ROOT"
npm install
```

### 4. Sidecar directory

```bash
mkdir -p ~/.omnicursor
```

---

## Day-of setup (do this before the audience arrives)

Open **4 terminals** and leave them running.

### Terminal 1 — OmniDash server

```bash
cd "$OMNIDASH_ROOT"
OMNIDASH_DATA_SOURCE=file \
FIXTURES_DIR=/tmp/omnicursor-omnidash-fixtures \
npm run dev
```

Wait for `Local: http://localhost:5173` (or similar). Open that URL in a browser
tab and navigate to the **Live Event Stream** widget. Leave it visible.

> `OMNIDASH_DATA_SOURCE=file` is required — without it the server defaults to
> SQLite and ignores the fixtures directory entirely.

### Terminal 2 — OmniCursor sidecar (Option C)

```bash
cd "$OMNICURSOR_ROOT"
bash scripts/run_sidecar.sh --publisher omnidash
```

Expected output:
```
sidecar starting | publisher=omnidash outbox=~/.omnicursor/outbox.jsonl socket=~/.omnicursor/emit.sock interval=2.0s
socket listener bound to ~/.omnicursor/emit.sock
```

Leave it running. It polls every 2 seconds.

### Terminal 3 — Smoke test (verify the pipe end-to-end)

Run this once to confirm events flow from socket → OmniDash before the demo:

```bash
python3 -c "
import socket, json, pathlib
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(str(pathlib.Path.home() / '.omnicursor/emit.sock'))
msg = {
    'event_type': 'session.outcome',
    'payload': {
        'session_id': 'smoke-preflight',
        'outcome': 'success',
        'matched_agent': 'debugging-agent',
        'matched_confidence': 0.92,
    }
}
s.sendall((json.dumps(msg) + '\n').encode())
print(s.recv(256).decode())
"
```

Expected response: `{"status": "queued", "event_id": "..."}`.

Within 2–3 seconds the OmniDash Live Event Stream widget should show the event.
If it does not appear, check the sidecar terminal for errors.

### Terminal 4 — Cursor (your working IDE)

Open Cursor pointed at the OmniCursor repo root. The repo already has hooks
and skills configured — no extra setup needed.

---

## Act 1 — Ticket-to-code pipeline (~8 min)

### Step 1 — Create a ticket from a task description

In Cursor's composer, type:

```
Add a prompt_length field to the session outbox schema so we can track
how long each prompt was. /plan-ticket
```

OmniCursor will automatically:
1. Read the codebase to understand `session_outbox.py`
2. Generate a YAML ticket contract
3. Call `tracker.create_issue` → creates a Linear ticket (e.g. `OMN-XX`)
4. Report the ticket URL

**Narrate:** "OmniCursor read the repo, determined what the task requires,
and registered it in Linear — no manual ticket writing."

### Step 2 — Execute the ticket autonomously

Still in Cursor's composer, type:

```
/execute-plan — implement OMN-XX
```

(Replace `OMN-XX` with the ticket ID from Step 1.)

OmniCursor drives the full pipeline unattended:
1. Reads the Linear ticket via MCP
2. Identifies files to change (`session_outbox.py`, relevant tests)
3. Implements the change
4. Runs `pytest tests/ -q`
5. Opens a PR via `gh pr create`
6. Updates the Linear ticket to Done

**Step away from the keyboard after typing the command.** This is the key
moment — the audience should see the pipeline running with no human input.

**Narrate while it runs:** "One command. OmniCursor reads the ticket contract,
writes the code, runs the test suite, opens the PR, and closes the ticket —
fully unattended."

### Step 3 — Show the result

When Claude finishes, show:
- The PR URL in the Cursor output
- The Linear ticket status: Done
- The diff: `src/omnicursor/session_outbox.py` has the new field

**Narrate:** "From a one-line description to a merged-ready PR. The ticket is
the contract; the implementation follows the contract."

---

## Act 2 — Option C observability (~5 min)

### Step 1 — Point at the sidecar terminal

Switch to Terminal 2. Show the drain log lines that appeared while Act 1 ran:

```
drainer: published session.outcome for session <id>
drainer: published utilization.scoring.requested for session <id>
```

**Narrate:** "Every time a Cursor session ends, our stop hook emits a structured
event over a Unix socket to the sidecar. The sidecar drains it to OmniDash — or
to Kafka in production."

### Step 2 — Show OmniDash

Switch to the OmniDash browser tab.

Point out:
- The session that just ran appears in the Live Event Stream
- Fields: `session_id`, `outcome: success`, `matched_agent`, `matched_confidence`
- Timestamp is within seconds of the session ending

**Narrate:** "This is the same event bus OmniClaude uses. The event format
matches `omniintelligence`'s expected schema — so omniintelligence can consume
it, update pattern weights, and inject those patterns into the next Cursor
session. That's the learning loop."

### Step 3 — Show the durable outbox (optional, 1 min)

```bash
tail -f ~/.omnicursor/outbox.jsonl | python3 -m json.tool
```

**Narrate:** "The outbox is the durability layer. If the sidecar is down, events
accumulate here and drain when it restarts — no data loss. This is the same
pattern OmniClaude uses with its emit daemon."

### Step 4 — Show the architecture diagram (optional)

```
Cursor IDE
  └─ stop hook (stop.py)
       └─► ~/.omnicursor/emit.sock
             └─► sidecar (socket_listener)
                   └─► ~/.omnicursor/outbox.jsonl   (durable)
                         └─► drain_loop (2s tick)
                               ├─► OmniDash fixtures  (demo)
                               └─► Kafka/Redpanda      (production)
                                     └─► omniintelligence
                                           └─► pattern injection
                                                 └─► next Cursor session
```

**Narrate:** "Option C puts OmniCursor on the same infrastructure as the rest of
OmniNode. The gap between Cursor and Claude Code closes at the event bus level."

---

## Troubleshooting

### OmniDash shows no events

1. Confirm `OMNIDASH_DATA_SOURCE=file` is set in Terminal 1. Kill and restart if needed.
2. Check `/tmp/omnicursor-omnidash-fixtures/` exists and has files:
   ```bash
   ls /tmp/omnicursor-omnidash-fixtures/onex.snapshot.projection.live-events.v1/
   ```
3. If the directory is empty, the sidecar did not drain. Check Terminal 2 for errors.

### Sidecar socket error on start

The sidecar cleans up stale sockets automatically. If it still fails:
```bash
rm -f ~/.omnicursor/emit.sock
cd "$OMNICURSOR_ROOT" && bash scripts/run_sidecar.sh --publisher omnidash
```

### Linear MCP not responding

Restart Cursor. MCP servers are started per IDE session. If still failing, check
`~/.cursor/mcp.json` has the `linear` entry and the API key is set.

### pytest fails during execute-plan

Claude will attempt up to 2 self-correction cycles. If tests still fail, it will
mark the ticket blocked and report what it tried. This is fine for the demo —
show the Linear comment as evidence of autonomous error reporting.

### Reset OmniDash between runs

```bash
rm -rf /tmp/omnicursor-omnidash-fixtures
```

The next drain cycle recreates the directory.

---

## Key env vars

| Variable | Where | Effect |
|---|---|---|
| `OMNIDASH_DATA_SOURCE=file` | Terminal 1 (OmniDash server) | Read projections from fixture files instead of SQLite |
| `FIXTURES_DIR` | Terminal 1 | Root directory served by OmniDash |
| `INTELLIGENCE_SERVICE_URL` | Cursor env | omniintelligence HTTP API for per-prompt pattern injection (default: `http://localhost:8053`) |
| `OMNICURSOR_CONTEXT_API_TIMEOUT_MS` | Cursor env | Timeout for API pattern fetch in ms (default: 900) |
| `OMNICURSOR_SIDECAR_INTERVAL` | Terminal 2 | Drain poll interval in seconds (default: 2) |
| `KAFKA_BOOTSTRAP_SERVERS` | Terminal 2 | Broker address when using `--publisher kafka` |

---

## Quick reference — skill commands

| Command | What it does |
|---|---|
| `/plan-ticket <description>` | Generates YAML contract, creates Linear ticket |
| `/plan-to-tickets <plan-file>` | Creates one epic + one ticket per plan task |
| `/execute-plan <plan-file>` | Full pipeline: review → tickets → implement → PR |
| `/hostile-reviewer --pr <N> --repo <owner/repo>` | Adversarial multi-model PR review |
| `/recap` | Summarises the current session before handing off |

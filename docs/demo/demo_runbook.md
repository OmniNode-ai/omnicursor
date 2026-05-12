# OmniCursor Demo Runbook — Options B+C (Full Intelligence Stack)

Three-act demo. Total time: ~20 minutes.

- **Act 1** — Agent routing: OmniCursor reads the prompt, selects the right agent,
  and injects learned patterns into the system message before the model sees anything.
- **Act 2** — Ticket-to-PR pipeline: one description becomes a Linear ticket, the
  omnimarket bridge implements it, opens a PR, watches CI, and merges — unattended.
- **Act 3** — The learning loop: the session outcome flows into omniintelligence via
  Kafka, pattern weights update, and the next prompt gets smarter context automatically.

Set this once before starting:

```bash
export OMNICURSOR_ROOT=<absolute path to OmniCursor worktree>
# e.g. export OMNICURSOR_ROOT=/home/andyw/cs490/omninode/OmniCursor/.worktrees/intelligence-option-bc
```

---

## The full pipeline

```
User prompt
  └─► user-prompt-submit.py
        ├─► GET /api/v1/patterns (omniintelligence, Option B read)
        │     └─► fallback: local learned_patterns.json
        ├─► 3-strategy agent scoring → best-fit agent selected
        └─► injects agent persona + patterns into system message

/execute-plan typed
  └─► plan-review → plan-to-tickets → Linear tickets created
  └─► run_ticket_pipeline(ticket_id) via omnimarket bridge
        └─► IMPLEMENT → LOCAL_REVIEW → CREATE_PR → CI_WATCH → AUTO_MERGE → DONE

Session ends (stop.py)
  ├─► classifies outcome (success/failed/abandoned)
  ├─► writes outbox record → ~/.omnicursor/outbox.jsonl  (Option C durable)
  ├─► emits session.outcome → Unix socket → sidecar → Kafka/Redpanda
  └─► updates local learned_patterns.json

Sidecar drain loop (every 2s)
  └─► omniintelligence consumes events → updates pattern weights in Postgres

Next prompt
  └─► GET /api/v1/patterns returns updated weights → better context injected
       └─► loop closes
```

---

## Prerequisites (one-time)

### 1. Python venv

```bash
cd "$OMNICURSOR_ROOT"
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Docker

```bash
docker info >/dev/null 2>&1 && echo "Docker OK"
```

First `docker compose up` builds omniintelligence from source — allow **5–10 minutes**.
Subsequent starts are instant (images cached).

### 3. Omnimarket

Ensure `OMNIMARKET_ROOT` points to a local omnimarket checkout. The omnimarket bridge
uses this to invoke `node_ticket_pipeline` via subprocess.

```bash
export OMNIMARKET_ROOT=/home/andyw/cs490/omninode/omnimarket
```

### 4. Linear MCP

Verify `~/.cursor/mcp.json` has a `linear` entry with a valid API key.

Quick check — open Cursor and type `/plan-ticket test`. If it calls `tracker.list_teams`
without erroring, Linear MCP is live.

### 5. gh CLI

```bash
gh auth status
```

The ticket pipeline uses `gh pr create` and `gh run watch`. If not authenticated,
run `gh auth login`.

### 6. Sidecar directory

```bash
mkdir -p ~/.omnicursor
```

---

## Day-of setup (do this before the audience arrives)

Open **3 terminals** and leave them running.

### Terminal 1 — Full B+C stack (compose + sidecar)

```bash
cd "$OMNICURSOR_ROOT"
source .venv/bin/activate
bash scripts/run_bc_stack.sh
```

Starts Redpanda, Postgres, Valkey, and omniintelligence, waits for the reducer to be
healthy, then launches the sidecar with Kafka publishing enabled.

Expected output:

```
Starting compose stack...
intelligence-reducer is healthy.

Starting OmniCursor sidecar (publisher=kafka)...
  INTELLIGENCE_SERVICE_URL=http://localhost:18091
  OMNICURSOR_PATTERN_SYNC_HTTP=1

sidecar starting | publisher=kafka outbox=~/.omnicursor/outbox.jsonl socket=~/.omnicursor/emit.sock interval=2.0s
socket listener bound to ~/.omnicursor/emit.sock
```

### Terminal 2 — Outbox watcher + preflight smoke test

```bash
cd "$OMNICURSOR_ROOT"
python3 scripts/watch_outbox.py
```

Then in a separate shell, confirm the full pipe is live:

```bash
python3 scripts/smoke_test.py
```

Expected: `{"status": "queued", "event_id": "..."}` from smoke test, and a color-coded
`SESSION OUTCOME` block in Terminal 2 within 2 seconds.

### Terminal 3 — Cursor (your working IDE)

Open Cursor pointed at `$OMNICURSOR_ROOT`. Hooks and skills are already configured.

---

## Act 1 — Agent routing and pattern injection (~3 min)

### Step 1 — Submit any prompt and show what happened

In Cursor's composer, type a realistic dev task:

```
I need to debug why the session outbox is writing duplicate entries
```

After the response starts, switch to Terminal 2. Show the hook event:

```
── HOOK  user-prompt-submit  conv=a3f8b2c1…
  agent    : debugging-agent  score=0.81
```

**Narrate:** "Before the model saw a single token, OmniCursor scored this prompt
against 18 agents, matched it to the debugging agent with 81% confidence, and
injected that agent's persona plus any relevant learned patterns into the system
message. The model is already working with the right context."

### Step 2 — Show the pattern injection (if patterns exist)

If `~/.omnicursor/learned_patterns.json` has entries, point out the `patterns injected`
field in Terminal 2. If it shows 0 at the start of the demo — that's honest and expected:

**Narrate:** "No patterns yet — this is the first session. By the end of the demo
you'll see how that changes."

---

## Act 2 — Ticket-to-PR pipeline (~10 min)

### Step 1 — Create a ticket from a description

In Cursor's composer, type:

```
Add a prompt_length field to the session outbox schema so we can track
how long each prompt was. /plan-ticket
```

OmniCursor will:
1. Read the codebase to understand `session_outbox.py`
2. Generate a YAML ticket contract
3. Call `tracker.create_issue` → creates a Linear ticket (e.g. `OMN-XX`)
4. Report the ticket URL

**Narrate:** "OmniCursor read the repo, wrote the contract, and registered the
ticket in Linear. No manual ticket writing."

### Step 2 — Run the full pipeline

Type:

```
/execute-plan — implement OMN-XX
```

(Replace `OMN-XX` with the ticket ID from Step 1.)

**Step away from the keyboard.** The omnimarket bridge takes over:

1. Reads the Linear ticket
2. Implements the change (`session_outbox.py` + tests)
3. Runs local review loop
4. Pushes branch, opens PR via `gh pr create`
5. Watches CI via `gh run watch`
6. Auto-merges when CI passes
7. Marks ticket Done in Linear

**Narrate while it runs:** "One command. The omnimarket bridge drives the full
pipeline — implement, review, PR, CI, merge, done. No human in the loop."

### Step 3 — Show the result

When the pipeline finishes:
- PR URL in Cursor output — click it
- Linear ticket status: Done
- Diff: `src/omnicursor/session_outbox.py` has the new `prompt_length` field

**Narrate:** "From a one-sentence description to a merged PR. The ticket is the
contract; the pipeline executes the contract."

---

## Act 3 — The learning loop (~5 min)

### Step 1 — Show the outbox watcher (Terminal 2)

Switch to Terminal 2. The Act 2 session is already there in color:

```
── SESSION OUTCOME  conv=437b7ae7…
  outcome  : SUCCESS
  agent    : documentation-architect  conf=0.73
  prompts  : 3   files edited: 2   patterns injected: 0
  reason   : files edited + completion marker

── SOCKET EVENT  utilization.scoring.requested  session=437b7ae7…
  patterns : auto-5f38e3a94eac
```

**Narrate:** "When the session ended, the stop hook wrote a structured record —
agent used, outcome, files changed, patterns injected — and emitted it over a
Unix socket to the sidecar."

### Step 2 — Show the sidecar terminal (Terminal 1)

Switch to Terminal 1:

```
drainer: kafka.publish session.outcome → onex.evt.omnicursor.session-outcome.v1
drainer: kafka.publish utilization.scoring.requested → onex.cmd.omniintelligence.utilization-scoring.v1
```

**Narrate:** "The sidecar published those events to Redpanda. omniintelligence
consumed them and updated its pattern weights in Postgres based on what worked."

### Step 3 — Submit another prompt and show the loop closed

Type any prompt in the same domain in Cursor. Then show Terminal 2:

```
── HOOK  user-prompt-submit  conv=b9d3e7f2…
  agent    : documentation-architect  score=0.73
  patterns injected: 2
```

**Narrate:** "The next prompt fetched updated patterns from omniintelligence and
injected them. The model now has context shaped by the previous session's outcome.
Every session makes the next one smarter — that's the loop."

### Step 4 — Show the full architecture (optional)

```
User prompt
  └─► OmniCursor hook
        ├─► GET /api/v1/patterns ◄──────────────────────┐
        └─► agent routing + pattern injection            │
                                                         │
/execute-plan                                            │
  └─► omnimarket bridge                                  │
        └─► implement → PR → CI → merge                 │
                                                         │
Session ends                                             │
  └─► outbox → sidecar → Kafka → omniintelligence        │
                                    └─► weights updated ─┘
```

**Narrate:** "OmniCursor is the Cursor-native surface. omnimarket is the execution
engine. omniintelligence is the brain that learns. Option B reads from it; Option C
writes to it. Together they put Cursor on the same intelligence infrastructure as
OmniClaude."

---

## Stopping the stack

```bash
bash scripts/run_bc_stack.sh --down
```

---

## Troubleshooting

### No events in Terminal 2 after session ends

1. Check Terminal 1 — sidecar should show drain lines. If not, the stop hook didn't fire.
   Make sure Cursor is opened on `$OMNICURSOR_ROOT`.
2. Check the outbox directly: `tail -5 ~/.omnicursor/outbox.jsonl`

### run_ticket_pipeline fails or is not available

Confirm `OMNIMARKET_ROOT` is set and points to a valid checkout:
```bash
ls "$OMNIMARKET_ROOT/src/omnimarket/nodes/node_ticket_pipeline"
```
Confirm the omnimarket MCP server is running in Cursor (check MCP status in Cursor settings).

### Sidecar socket error on start

```bash
rm -f ~/.omnicursor/emit.sock && bash scripts/run_bc_stack.sh
```

### intelligence-reducer not healthy

```bash
docker compose logs intelligence-reducer --tail=30
docker compose ps
```

First-time build takes 5–10 minutes. If it fails, Postgres may not be ready yet —
wait 30 seconds and try again.

### Linear MCP not responding

Restart Cursor (MCP servers start per session). Check `~/.cursor/mcp.json` has the
`linear` entry and the API key is valid.

### gh CLI not authenticated

```bash
gh auth login
```

---

## Key env vars

| Variable | Set by | Effect |
|---|---|---|
| `OMNICURSOR_ROOT` | You | Path to this worktree |
| `OMNIMARKET_ROOT` | You | Path to local omnimarket checkout |
| `INTELLIGENCE_SERVICE_URL` | `run_bc_stack.sh` | omniintelligence reducer for per-prompt pattern fetch (`http://localhost:18091`) |
| `OMNICURSOR_PATTERN_SYNC_HTTP` | `run_bc_stack.sh` | `1` = pull updated patterns from omniintelligence after each session |
| `KAFKA_BOOTSTRAP_SERVERS` | `run_bc_stack.sh` | Redpanda broker (`localhost:19092`) |

---

## Quick reference — skills

| Command | What it does |
|---|---|
| `/plan-ticket <description>` | Generates YAML contract, creates Linear ticket |
| `/execute-plan <ticket or plan>` | Full pipeline via omnimarket: implement → PR → CI → merge |
| `/hostile-reviewer --pr <N> --repo <owner/repo>` | Adversarial multi-model PR review |
| `/recap` | Summarises the current session |
| `/systematic-debugging` | Structured root-cause debugging |

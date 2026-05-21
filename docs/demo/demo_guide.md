# OmniCursor — Local Demo Guide (Option C)

> **Plain English. No jargon. Read this — especially the "Mental model" — before running the demo.**
> Last validated: 2026-05-11 against `main`. 692 tests passing.

---

## TL;DR — what this demo proves

OmniCursor turns Cursor into an AI coding assistant that **learns from your work** and **keeps a record of every session** — all without connecting to any external server.

By the end of this guide you will have:

1. **Seen the hook layer fire** — when you submit a prompt, Cursor's hook classifies it, picks an agent, and injects learned patterns into the model context.
2. **Seen the durable outbox grow** — every session that ends writes a structured record to `~/.omnicursor/outbox.jsonl`.
3. **Seen the dashboard render those records live** — a local bridge feeds the outbox into OmniDash with no Kafka, no cloud.

---

## Mental model — OmniCursor has TWO layers

Read this section **before** running the scenarios. It solves 90% of the "what am I looking at?" confusion.

```text
┌────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — "While you type a prompt"                               │
│  Invisible to humans, visible only to the AI model.                │
│                                                                    │
│  • Hook reads your prompt                                          │
│  • Picks an agent (debug-intelligence, pr-review, …)               │
│  • Injects relevant learned patterns                               │
│  • Output: a `systemMessage` block delivered to Cursor's model     │
│                                                                    │
│  Where the metadata is recorded: ~/.omnicursor/events.jsonl        │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ session ends → stop hook runs
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — "After a session ends"                                  │
│  Visible in the dashboard.                                         │
│                                                                    │
│  • stop hook aggregates events from Layer 1                        │
│  • Writes one "postcard" to the outbox                             │
│  • Bridge copies it to fixtures                                    │
│  • Express server serves them as HTTP                              │
│  • Dashboard widget renders them                                   │
│                                                                    │
│  Where the postcards are recorded: ~/.omnicursor/outbox.jsonl      │
└────────────────────────────────────────────────────────────────────┘
```

**CRITICAL:** the rich "agent routing + injected patterns + delegation rule" block from Layer 1 is **NOT** visible in the dashboard. The dashboard only shows Layer 2 postcards (one row per ended session). If you want to inspect what was injected for a given prompt, read `~/.omnicursor/events.jsonl`.

---

## What runs during the demo (no Docker, no cloud needed)

| Component | What it does | Where it lives |
|---|---|---|
| **Cursor hooks** | Fire automatically when you type a prompt or edit a file | Inside Cursor — you don't launch them manually |
| **events.jsonl** | Raw diary of every hook event | `~/.omnicursor/events.jsonl` |
| **learned_patterns.json** | Stores learned patterns between sessions | `~/.omnicursor/learned_patterns.json` |
| **outbox.jsonl** | Stores a "postcard" of every ended session | `~/.omnicursor/outbox.jsonl` |
| **OmniDash bridge** | Reads the outbox, writes fixtures the dashboard can consume | You launch it manually (Scenario 6, Terminal 3) |
| **OmniDash Express server** | Serves the fixtures over HTTP on **port 3002** | You launch it manually (Scenario 6, Terminal 1) |
| **OmniDash UI (Vite)** | Renders the dashboard in your browser on **port 3001** | You launch it manually (Scenario 6, Terminal 2) |

That's it. No database, no Kafka, no Docker required for the core demo.

---

## Before you start

Run these once, in this order. The npm install takes ~30s; everything else is seconds.

```bash
# 1. Activate the Python venv
source .venv/bin/activate

# 2. Confirm the test suite is green (expect ~692 passed in <2s)
python -m pytest -q

# 3. Confirm lint is clean
python -m ruff check src/ tests/ .cursor/hooks/
# Expected: All checks passed!

# 4. Install OmniDash dependencies (only needed for Scenario 6, ~30s)
cd omnidash && npm install && cd ..

# 5. (Recommended) Back up your local state so the demo doesn't mix with real work
BACKUP=~/.omnicursor/demo-backup-$(date +%s)
mkdir -p "$BACKUP"
cp ~/.omnicursor/outbox.jsonl          "$BACKUP/" 2>/dev/null || true
cp ~/.omnicursor/learned_patterns.json "$BACKUP/" 2>/dev/null || true
echo "Backup at $BACKUP"
```

---

## How the demo simulates hooks without using Cursor itself

Hooks normally fire automatically while you use Cursor. For a **reproducible** demo run, you can also simulate any hook by piping JSON into its script. This is how this guide verifies each scenario without depending on the Cursor UI.

| Hook event | Simulation command (run from repo root) |
|---|---|
| `beforeSubmitPrompt` | `echo '{"prompt":"…","conversation_id":"sid-1","generation_id":"g1"}' \| python3 .cursor/hooks/scripts/user-prompt-submit.py` |
| `afterFileEdit` | `echo '{"file_path":"path/to/file.py","edits":[{"type":"create"}],"conversation_id":"sid-1"}' \| python3 .cursor/hooks/scripts/post-edit.py` |
| `stop` | `echo '{"conversation_id":"sid-1","status":"completed"}' \| python3 .cursor/hooks/scripts/stop.py` |

Each scenario below shows **both flavours**: type the prompt into Cursor as normal **or** run the CLI simulation. They produce the same files on disk.

---

## The Demo — 6 Scenarios

### Scenario 1 — Automatic Prompt Routing

**What happens:** when you submit a prompt, the `beforeSubmitPrompt` hook classifies it and picks the best agent — without you doing anything.

**Option A — type this prompt in Cursor:**
```
Debug why pattern_sync should never overwrite learned_patterns.json when omniintelligence is offline. Inspect the current implementation and list the evidence. Do not edit files. Finish with the word done.
```

**Option B — simulate it from the CLI:**
```bash
echo '{"prompt":"Debug why pattern_sync should never overwrite learned_patterns.json when omniintelligence is offline. Inspect the current implementation and list the evidence. Do not edit files. Finish with the word done.","conversation_id":"demo-s1","generation_id":"g1"}' \
  | python3 .cursor/hooks/scripts/user-prompt-submit.py
```

**Verify (the hook writes to `~/.omnicursor/events.jsonl`, not the terminal):**
```bash
tail -n 200 ~/.omnicursor/events.jsonl | grep '"prompt_classified"' | tail -1 | python -m json.tool
```
You'll see something like:
```json
{
  "event": "prompt_classified",
  "matched_agent": "debug-intelligence",
  "score": 0.95,
  "reason": "Exact trigger: 'debug'",
  "patterns_injected": 3,
  "hook_duration_ms": 19
}
```

**Why it matters:** the hook used three matching strategies (exact match → fuzzy match → keyword overlap). It picked the debugging agent at 0.95 confidence in under 20ms. No manual selection, no API call.

**Reality check — agent vocabulary in this repo:**

Only a handful of agents have JSON configs in `.cursor/agents/`. Trigger words that route to a specific agent today:

| Prompt contains… | Routes to | Confidence |
|---|---|---|
| `debug`, `traceback`, `regression`, `flaky test` | `debug-intelligence` | 0.95 |
| `pr review`, `merge ready`, `code review` | `pr-review` | 0.95 |
| `hostile review`, `tear apart` | `hostile-reviewer` | 0.95 |
| `handoff`, `session summary` | `content-summarizer` | 0.95 |

Words like `brainstorm`, `plan`, `ticket`, `recap` will currently fall through to `polymorphic-agent` (the fallback). This is **expected behaviour, not a bug** — only agents with JSON configs score above `HARD_FLOOR = 0.55`. Add agents under `.cursor/agents/*.json` to extend the vocabulary.

---

### Scenario 2 — Auto-Lint After Every Edit

**What happens:** every time Cursor edits a Python file, the `afterFileEdit` hook automatically runs `ruff check` diagnostically and logs the findings. It **never** modifies the file.

**Option A — type this prompt in Cursor:**
```
Create eval/demo_autolint.py with an intentional unused import for hook-demo purposes. Do not fix the lint issue. Add one tiny function and finish with done.
```

**Option B — simulate it from the CLI:**
```bash
mkdir -p eval
cat > eval/demo_autolint.py <<'PY'
import os

def demo_function():
    return "ok"
PY

echo '{"file_path":"eval/demo_autolint.py","edits":[{"type":"create"}],"conversation_id":"demo-s2"}' \
  | python3 .cursor/hooks/scripts/post-edit.py
```

**Verify:**
```bash
tail -n 50 ~/.omnicursor/events.jsonl | grep '"file_edited"' | tail -1 | python -m json.tool
```
You'll see:
```json
{
  "event": "file_edited",
  "file_path": "eval/demo_autolint.py",
  "language": "python",
  "ruff_findings": 9,
  "tsc_findings": 0,
  "hook_duration_ms": 9
}
```

**Why it matters:** the hook never modifies the file — it only reports. Confirm with `cat eval/demo_autolint.py` that the unused import is still there.

---

### Scenario 3 — Patterns That Cross Sessions

**What happens:** a pattern seeded (or learned) in session A is automatically injected into session B's context.

**Step 1 — seed a pattern:**
```bash
python3 - <<'PY'
import json, time
from pathlib import Path

p = Path.home() / ".omnicursor" / "learned_patterns.json"
p.parent.mkdir(parents=True, exist_ok=True)
data = {"patterns": []}
if p.exists():
    try:
        data = json.loads(p.read_text())
    except Exception:
        data = {"patterns": []}

demo = {
    "pattern_id": "demo-pattern-omnicursor-preserve-marker",
    "domain": "debug_intelligence",
    "pattern": "debug demo marker pattern_sync learned_patterns",
    "keywords": ["demo_marker", "pattern_sync", "learned_patterns"],
    "description": "Demo: preserve DEMO_MARKER comments when editing demo files.",
    "weight": 1.0,
    "created_at": time.time(),
    "last_seen": time.time(),
    "injection_count": 0,
    "utilization_successes": 0,
}
patterns = [x for x in data.get("patterns", []) if x.get("pattern_id") != demo["pattern_id"]]
patterns.append(demo)
data["patterns"] = patterns
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"Pattern seeded. Total patterns: {len(patterns)}")
PY
```

**Step 2 — submit a fresh prompt (Option A — Cursor):**
```
Debug this demo workflow: when editing files that contain DEMO_MARKER, preserve that marker and mention done when complete. Inspect or create docs/demo-pattern.md. Finish with done.
```

**Step 2 — Option B — CLI:**
```bash
echo '{"prompt":"Debug this demo workflow: when editing files that contain DEMO_MARKER, preserve that marker and mention done when complete. Inspect or create docs/demo-pattern.md. Finish with done.","conversation_id":"demo-s3","generation_id":"g1"}' \
  | python3 .cursor/hooks/scripts/user-prompt-submit.py > /dev/null
```

**Verify:**
```bash
tail -n 20 ~/.omnicursor/events.jsonl | grep '"prompt_classified"' | tail -1 | python -m json.tool
```
You'll see `"injected_pattern_ids"` containing `"demo-pattern-omnicursor-preserve-marker"`.

**Why it matters:** the assistant remembered something from a previous session and used it automatically. This is the core of the "learning" feature.

---

### Scenario 4 — Durable Session Record

**What happens:** every time a session ends, the `stop` hook writes a structured record to `~/.omnicursor/outbox.jsonl`. This is the "outbox" — a contract a cloud service can drain later.

**Trigger:** close a Cursor session normally, **or** simulate it:
```bash
echo '{"conversation_id":"demo-s3","status":"completed"}' \
  | python3 .cursor/hooks/scripts/stop.py
```

**Inspect the latest postcard:**
```bash
tail -n 1 ~/.omnicursor/outbox.jsonl | python -m json.tool
```
You'll see:
```json
{
  "schema_version": "omnicursor.session_outcome.v1",
  "session_outcome": "success",
  "files_edited": 1,
  "matched_agent": "debug-intelligence",
  "patterns_injected": 3,
  "injected_pattern_ids": ["demo-pattern-omnicursor-preserve-marker", "..."],
  "ended_at": "2026-..."
}
```

To produce a **failed** outcome instead, swap `"completed"` for `"failed"` in the stop simulation — the record will have `"session_outcome": "failed"` and the `Live Event Stream` widget will render a red **ERROR** badge for it.

**Why it matters:** this file is the handoff point to cloud infrastructure. When the Kafka integration ships, it will drain this file to the cloud — but nothing breaks while that infrastructure is absent.

---

### Scenario 5 — Hooks Off, System Still Works (MCP Fallback)

**What happens:** even if Cursor's hooks are disabled, the Omnimarket bridge is still available via MCP (or by direct subprocess call).

**Run it:**
```bash
OMNIMARKET_ROOT=/path/to/omnimarket \
  python -c "
import json
from omnicursor.omnimarket_bridge import run_local_review
print(json.dumps(run_local_review(dry_run=True), indent=2, default=str))
"
```

> Adjust `OMNIMARKET_ROOT` to your local checkout. If you skip the variable, the bridge falls back to `./omnimarket-main` as a dev convenience.

**Expected output (first lines):**
```json
{
  "ok": true,
  "returncode": 0,
  "state": {
    "current_phase": "init",
    "dry_run": true,
    "issues_found": 0
  }
}
```

**Why it matters:** hooks and Omnimarket are two independent layers. If one fails, the other keeps the system working.

---

### Scenario 6 — Sessions Live in OmniDash (optional, but visual)

**What happens:** session records from the outbox appear in real time in an OmniDash dashboard widget — no Kafka, no cloud.

**Open 3 terminals (each in a new tab/window):**

**Terminal 1 — Express bridge (serves fixtures on port 3002):**
```bash
cd /path/to/omnidash
OMNIDASH_DATA_SOURCE=file \
FIXTURES_DIR=/tmp/omnicursor-omnidash-fixtures \
npm run dev:server
```
Wait for: `[omnidash server] Listening on port 3002`.

**Terminal 2 — Vite dashboard (serves the UI on port 3001):**
```bash
cd /path/to/omnidash
VITE_DATA_SOURCE=http \
VITE_HTTP_DATA_SOURCE_URL=http://localhost:3002 \
npm run dev
```
Wait for: `VITE v5.x.x ready ... Local: http://localhost:3001/`.

> **Port heads-up:** the URL is **http://localhost:3001/**, not 5173. Older copies of this guide said 5173 — that's wrong for this setup. Trust whatever Vite prints.

**Terminal 3 — OmniCursor bridge (drains outbox into fixtures every 2s):**
```bash
cd /path/to/OmniCursor
bash scripts/run_omnidash_bridge.sh
```
This process runs silently. It writes JSON files into `/tmp/omnicursor-omnidash-fixtures/onex.snapshot.projection.live-events.v1/`.

**Sanity check from a 4th terminal:**
```bash
# Server up?
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3001/
# Expected: HTTP 200

# Server serving events?
curl -s 'http://localhost:3002/projection/onex.snapshot.projection.live-events.v1' \
  | python -c "import json,sys; print('events served:', len(json.load(sys.stdin)))"
# Expected: a positive number
```

**In the browser:**
1. Open **http://localhost:3001/**.
2. Click `+ Add first widget` (or `+ Add Widget` top-right).
3. In the Widget Library, search for **"Live Event Stream"** (category: *Activity*).
4. Drop it onto the canvas. It renders rows pulled from port 3002 immediately.
5. **Click any row** to expand the full payload (`session_id`, `correlation_id`, `injected_pattern_ids`, etc.).

**What you'll see in the widget:**

| Column | Example | Meaning |
|---|---|---|
| TIME | `17:00:21` | When the postcard arrived |
| NODE | 🟢 `ACTION` / 🟡 `TRANSFORMATION` / 🔴 `ERROR` | Type-coded badge |
| TOPIC | `onex.evt.omnicursor.session-outcome.v1` | Kafka topic name (informational) |
| DETAIL | `success · debug-intelligence · 2 files` | Summary line |

#### Widget catalog reality

The Widget Library shows **24 widgets across 4 categories**. For this local demo, **only one** has data:

| Widget | Will it show data? | Why |
|---|---|---|
| **Live Event Stream** | ✅ Yes | This is the only widget wired to read from `http://localhost:3002`. |
| **Event Stream** (Kafka) | ❌ Empty | Expects real Kafka. You're not running Kafka. |
| **Cost** widgets (11): Cost Trend, Cost by Model, Cost by Repo, Cost Summary, Token Usage, Cost Savings Overview, Delegation Savings, AB Model Cost Compare, … | ❌ Empty | Designed for OmniMarket LLM-spend data. Not connected here. |
| **Activity, Quality, Health** widgets (11): Routing Decisions, Intent Distribution, Session Timeline, Model Routing, Quality Scores, Receipt Gate, Quality Gate, Delegation Metrics, Baselines ROI, Readiness Gate, … | ❌ Empty | Designed for OmniMarket / OmniNode service data. Not connected here. |

**Bottom line:** for this demo, the Widget Library = **one** useful widget + 23 catalogue placeholders. Don't waste time clicking through them.

**Why it matters:** the full observability loop works locally. No Kafka, no cloud, no infrastructure — just the local outbox feeding a real dashboard.

---

## What the Demo Does NOT Prove

Be honest about this with your team. The demo does **not** show:

- **Real omniintelligence scoring.** The "utilization" score is a proxy (session success ≈ pattern was useful). A real LLM check of whether the pattern was actually applied is future work.
- **Cloud / Kafka integration.** The outbox is ready to drain to Redpanda, but that pipe has not been built yet.
- **Production OmniDash.** The Live Event Stream is a generic widget reading local files. A dedicated OmniCursor view in production OmniDash is future work.
- **The injected `systemMessage` rendered.** Layer 1's rich routing block is consumed by the Cursor model and never persisted in full. You can only see its **metadata** in `events.jsonl` (`matched_agent`, `injected_pattern_ids`, `score`, …) — never the rendered Markdown that the model actually saw.

---

## Inspecting the three files that ARE the product

Forget the dashboard — these three files in `~/.omnicursor/` are where the real work lives:

```bash
ls -lh ~/.omnicursor/{events.jsonl,learned_patterns.json,outbox.jsonl}
```

| File | What's in it | How to read it |
|---|---|---|
| `events.jsonl` | One JSON line per hook event (`prompt_classified`, `file_edited`, `session_stop`, …) | `tail -n 5 ~/.omnicursor/events.jsonl` (then `python -m json.tool` on a single line) |
| `learned_patterns.json` | The "notebook" — patterns and their `injection_count` / `utilization_successes` counters | `python -m json.tool < ~/.omnicursor/learned_patterns.json \| less` |
| `outbox.jsonl` | One JSON line per ended session — the "postcards" | `tail -n 5 ~/.omnicursor/outbox.jsonl` (one line at a time) |

**See which patterns are most trusted right now:**
```bash
python3 -c "
import json
from pathlib import Path
data = json.loads((Path.home()/'.omnicursor/learned_patterns.json').read_text())
print('Top 5 by utilization_successes:')
for p in sorted(data.get('patterns', []), key=lambda x: x.get('utilization_successes', 0), reverse=True)[:5]:
    print(f\"  inj={p.get('injection_count',0):3d}  succ={p.get('utilization_successes',0):3d}  weight={p.get('weight',0):.2f}  id={p.get('pattern_id','')[:50]}\")
"
```

A pattern with `inj=7 succ=7 weight=0.95` has been injected 7 times into prompts and all 7 sessions ended in success → the system trusts it heavily for similar prompts in the future. **That counter changing over time is the "learning".**

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Live Event Stream` widget shows "No events" | Bridge (Terminal 3) not running, or Vite pointing to the wrong server | Confirm `scripts/run_omnidash_bridge.sh` is alive; confirm `VITE_HTTP_DATA_SOURCE_URL=http://localhost:3002` |
| `Event Stream` (Kafka) widget shows "No events" | This is the **Kafka** widget — needs Kafka, not in this demo | Don't use that widget. Use **Live Event Stream** instead. |
| Vite prints port 3001 instead of 5173 | OmniDash's `vite.config.ts` pins port 3001 | Use 3001 — that's the correct URL. |
| `curl http://localhost:3002/api/event-bus` returns 404 | Wrong endpoint | Use `http://localhost:3002/projection/onex.snapshot.projection.live-events.v1` |
| Tests fail with import errors | Wrong venv or missing dev deps | `source .venv/bin/activate && pip install -e ".[dev]"` |
| `omnimarket_bridge` errors out | `OMNIMARKET_ROOT` not set and no `omnimarket-main/` checkout | Set `OMNIMARKET_ROOT` to your local checkout or clone `omnimarket` next to this repo |
| Demo mixed with my real session data | Skipped the backup step | Restore from `~/.omnicursor/demo-backup-*` |
| Hook seems not to fire while typing in Cursor | Hooks disabled or `.cursor/hooks.json` renamed | `ls .cursor/hooks.json` should exist; restart Cursor after restoring it |

---

## Quick Verification (run before any demo session)

```bash
# Tests green?
python -m pytest -q
# Expected: 692 passed in ~2s

# Lint clean?
python -m ruff check src/ tests/ .cursor/hooks/
# Expected: All checks passed!

# Bridge smoke (no OmniDash UI required)?
python -m omnicursor.drainer.omnidash_bridge \
  --outbox /tmp/smoke-outbox.jsonl \
  --cursor /tmp/smoke.cursor \
  --fixtures /tmp/omnicursor-omnidash-fixtures \
  --once
# Expected: exits 0, prints drainer stats
```

---

## Cleanup after the demo

```bash
# Stop the 3 background processes from Scenario 6
pkill -f "tsx watch server/index.ts" || true            # Express bridge
pkill -f "node .*vite" || true                          # Vite dashboard
pkill -f "omnicursor.drainer.omnidash_bridge" || true   # OmniCursor bridge

# Restore the pre-demo state (optional)
LATEST_BACKUP=$(ls -td ~/.omnicursor/demo-backup-* 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
  cp "$LATEST_BACKUP/outbox.jsonl"          ~/.omnicursor/ 2>/dev/null
  cp "$LATEST_BACKUP/learned_patterns.json" ~/.omnicursor/ 2>/dev/null
  echo "Restored from $LATEST_BACKUP"
fi

# Remove the demo file from Scenario 2 (if you created it)
rm -f eval/demo_autolint.py
```

> **Important:** the cleanup commands stop the demo *dashboard*. The Cursor *hooks* remain active — they live in `.cursor/hooks.json` and fire as part of your normal Cursor usage. They have no UI, no terminal output, no perceptible latency.

To **temporarily disable all hooks** (if a teammate prefers an OmniCursor-free experience):
```bash
mv .cursor/hooks.json .cursor/hooks.json.disabled
# Restart Cursor.
```
Restore with `mv .cursor/hooks.json.disabled .cursor/hooks.json` and restart Cursor.

---

## One-Line Summary Per Scenario

| # | Scenario | What it proves |
|---|----------|----------------|
| 1 | Prompt routing | Cursor classifies prompts automatically; agent picked in <20ms; no manual selection |
| 2 | Auto-lint | Every Python edit is checked with ruff; file is never modified |
| 3 | Pattern persistence | Patterns seeded in session A appear in session B's injection list |
| 4 | Durable outbox | Every session writes an `omnicursor.session_outcome.v1` record locally, cloud-ready |
| 5 | MCP fallback | Omnimarket bridge runs independently — if hooks are off, MCP still works |
| 6 | OmniDash live | Sessions render in a real dashboard widget within ~5s, no cloud needed |

---

## Elevator pitch for teammates

> *"OmniCursor is a memory layer for Cursor. When you type a prompt, it picks the right agent, injects patterns it learned from past sessions, and records every ended session into a local outbox that's ready to ship to a team server later. The dashboard is just a viewer for that outbox — the real value is the invisible work the hooks do for every prompt and every file edit."*

That's the whole product. The Live Event Stream widget is the visible proof. The three files in `~/.omnicursor/` are the durable artefact. Everything else is plumbing.

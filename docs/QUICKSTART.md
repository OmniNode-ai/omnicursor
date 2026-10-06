# OmniCursor Quickstart

OmniCursor is a [Cursor plugin](https://cursor.com/docs/plugins): agent routing, shell guards, session recaps, and 17 methodology skills. Install it once on your machine; it applies to **every project** you open in Cursor.

---

## Requirements

- [Cursor](https://cursor.com) (recent version with plugin support)
- Python 3.10+ on your PATH (hooks invoke `python3`; stdlib only)

---

## Step 1 — Obtain the source

```bash
git clone https://github.com/OmniNode-ai/OmniCursor ~/tools/OmniCursor
cd ~/tools/OmniCursor
```

## Step 2 — Install the plugin

```bash
./scripts/install-plugin.sh
```

This copies a curated runtime payload to `~/.cursor/plugins/local/omnicursor`.
The copy works after removing the source checkout. It contains no symlinks, venv,
project shim, secrets, caches or tests (including node tests). Reinstall after
changing the source; stale files disappear. The installer validates clean staging
before replacement and restores the previous copy if replacement fails.

Recognized old symlinks migrate automatically without changing their targets.
An unmarked manual copy is protected: move it to a backup **outside** `plugins/local`
before installing. A managed-install marker is stored outside the manifest.
`--dry-run` and `--status` make no writes. Plain `--uninstall` preserves user data;
`--uninstall --purge` remains an explicit, path-checked operation.

**Check status:**

```bash
./scripts/install-plugin.sh --status
```

## Step 3 — Reload Cursor

Restart Cursor or run **Developer: Reload Window** (`Ctrl+Shift+P`).

In **Settings → Rules**, confirm OmniCursor rules and skills appear. Set important rules to **Always** or **Agent Decides** as you prefer.

## Step 4 — Open any project

No per-repo setup. Hooks and rules load from the plugin install path for every workspace.

---

## What you get

### Hooks (automatic)

Seven Cursor lifecycle hooks load automatically — `sessionStart`,
`beforeSubmitPrompt`, `beforeShellExecution`, `afterFileEdit`, `postToolUse`,
`stop`, `sessionEnd`. Only **shell-guard** (`beforeShellExecution`) can block a
command; every other hook is observe/inject-only and always exits 0.

Full per-hook behavior: [README → Hooks](../README.md#hooks) ·
[ARCHITECTURE.md §4](./ARCHITECTURE.md#4-hooks).

### Rules (always-on + keyword)

Four rules are **always active** (`00`–`03`): ONEX vocabulary, codebase research policy, no-secrets guard, and OmniCursor/OmniMarket ownership boundary.

Ten others activate on keywords (brainstorm, plan, debug, PR review, handoff, recap, Linear tickets, execute-plan, etc.). See [`rules/README.md`](../rules/README.md).

### Skills (keyword-triggered)

Say the keyword in chat and Cursor reads the skill file and follows it.

**Slash menu (`/`):** Each skill uses YAML frontmatter with `name: onex-<slug>`. Typing `/` shows those ids (e.g. `onex-brainstorming`).

#### Bucket 1 — Pure methodology (works offline)

| Keyword / slash | Skill | What it does |
|-----------------|-------|--------------|
| `brainstorm` | onex-brainstorming | Structured ideation → design doc |
| `write a plan` | onex-writing-plans | Implementation plan with TDD tasks |
| `debug` / `root cause` | onex-systematic-debugging | 5-phase root cause analysis |
| `pr review` | onex-pr-review | Severity-classified review (CRITICAL / MAJOR / MINOR / NIT) |
| `pr polish` | onex-pr-polish | Pre-merge PR cleanup |
| `hostile review` | onex-hostile-reviewer | Adversarial code review |
| `defense in depth` | onex-defense-in-depth | Layered validation checklist |
| `docs sync` | onex-docs-reality-sync | Reconcile docs with code reality |
| `merge plan` | onex-merge-planner | Merge strategy for multi-branch work |
| `insights to plan` | onex-insights-to-plan | Turn research notes into a plan |
| `plan review` | onex-plan-review | Adversarial plan review (R1–R6) |
| `handoff` | onex-handoff | Session summary for the next chat |
| `recap` or `/recap` | onex-recap | Inline session recap; auto-injects previous recap at start |
| `worktree` | onex-using-git-worktrees | Git worktree workflow |

#### Bucket 3 — External services (Linear MCP)

Bucket 2 is retired at the skill level; the `12-plan-ticket` **rule** stays local-only (YAML template, no external calls). Canonical classification: [ARCHITECTURE.md §3](./ARCHITECTURE.md#3-skills).

| Keyword | Skill | Requires | What it does |
|---------|-------|----------|--------------|
| `create ticket` | onex-plan-ticket | Linear MCP | Turns a plan task into a Linear ticket (the rule's local YAML template still works offline) |
| `plan to tickets` | onex-plan-to-tickets | Linear MCP | Batch-create Linear tickets from a plan |
| `execute plan` | onex-execute-plan | Linear MCP (+ OmniMarket for node dispatch) | Autonomous ticket execution pipeline |

See [`skills/`](../skills/) for the full set. Architecture details: [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Optional: Linear MCP (Bucket 3 skills)

Skills like `onex-plan-to-tickets` and `onex-execute-plan` need the Linear MCP server.

**1. Add Linear's hosted MCP server to `~/.cursor/mcp.json`:**

```json
{
  "mcpServers": {
    "linear": {
      "url": "https://mcp.linear.app/mcp"
    }
  }
}
```

**2. Restart Cursor and authenticate** — Cursor prompts a browser OAuth flow
against your Linear workspace the first time the server is used (no API key
needed; hosted MCP uses OAuth).

**3. Verify** — open a Cursor chat and say "list my Linear teams". It should return your teams.

---

## Optional: OmniNode stack (patterns + events)

OmniCursor works fully offline with local pattern learning (`~/.omnicursor/learned_patterns.json`). To connect to the wider OmniNode stack:

1. Copy [`.env.omninode.example`](../.env.omninode.example) and set `OMNIMARKET_ROOT`, `INTELLIGENCE_SERVICE_URL`, etc.
2. Start local services: `docker compose up -d` (Redpanda, omniintelligence)
3. Enable HTTP pattern sync: `OMNICURSOR_PATTERN_SYNC_HTTP=1`
4. Event emission: hook events flow best-effort to the **shared platform emit daemon** (omnimarket `node_emit_daemon`) when it owns `~/.omnicursor/emit.sock` — there is no Cursor-side publisher to run.

See [ARCHITECTURE.md](./ARCHITECTURE.md) § Intelligence options for the A/B model.

---

## Updating OmniCursor

```bash
cd ~/tools/OmniCursor
git pull
./scripts/install-plugin.sh
```

`git pull` updates the source checkout only. Run the installer again to replace
the installed copy, then reload Cursor to use the updated plugin.

## Uninstalling the plugin

```bash
./scripts/install-plugin.sh --uninstall
```

Then reload Cursor. Local session data under `~/.omnicursor/` is not removed.

---

## Developer setup (contributing to OmniCursor)

```bash
cd ~/tools/OmniCursor
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" ruff # [dev] = pytest + jsonschema (manifest gate); ruff is a separate dep
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
pytest tests/ -v
ruff check src/ tests/ hooks/ scripts/ci/
```

CI runs the same checks on every PR to `main`.

Key contributor docs:

- [ARCHITECTURE.md](./ARCHITECTURE.md) — layers, buckets, routing, event emission
- [INDEX.md](./INDEX.md) — documentation map

---

## Privacy — what OmniCursor stores locally

OmniCursor writes session data to files under `~/.omnicursor/`:

**`events.jsonl`** — structured log of every hook event (prompt classifications, shell guard decisions, edit lint results, session outcomes). Contains the prompt text submitted to the router and the agent/confidence result.

**`learned_patterns.json`** — the pattern learning cache. Each record stores:

- `key`: a sorted keyword fingerprint extracted from the prompt (e.g. `"debug fix test TypeError"`) — not the full prompt
- `description`: `"Auto-learned: <first 60 chars of prompt> → <agent> (score X.XX)"` — captures up to 60 characters of prompt content
- `domain`, `weight`, `success_count`, `injection_count`, `utilization_successes`, `last_seen`

**The description field captures prompt content.** If your prompts contain secrets, credentials, PII, or sensitive project names, that content may appear in `learned_patterns.json`. OmniCursor does not transmit this file anywhere by default — it is local storage unless you enable `OMNICURSOR_PATTERN_SYNC_HTTP=1` (pull-only from a local omniintelligence service).

If you are working with sensitive material, avoid typing it directly into prompts or clear `~/.omnicursor/learned_patterns.json` periodically.


## Development hook source

| Option | Benefit | Cost |
|---|---|---|
| Keep the project shim — chosen | Test checkout edits without reinstalling | Keep two equivalent configurations and disable the installed plugin while using the shim |
| Remove project hooks | One distributed configuration | Lose direct checkout execution; reinstall the copy to test every change |

Use only one source at a time. In Cursor's plugin settings, disable OmniCursor
before opening this checkout with its `.cursor/hooks.json` shim. Verify one set of
local hook events for a new conversation. For plugin mode, enable OmniCursor,
reinstall, then use a foreign workspace with no OmniCursor project hooks and start
a separate conversation. Tests normalize the root prefix and compare all seven
shim bindings with `hooks/hooks.json`. There is no automatic deduplication.

## Optional runtime requirements

| Surface | External requirement |
|---|---|
| Offline hooks, routing, guards, state and learning | Compatible `python3` visible to Cursor; stdlib and copied code only. Ruff/TypeScript diagnostics are optional |
| Existing emit daemon | Socket reachable; `ensure_daemon()` pings before checking interpreters |
| Automatic daemon startup | `OMNICURSOR_DAEMON_PYTHON` points to an existing interpreter with OmniMarket installed. An invalid path disables startup; the copy has no `.venv` fallback |
| Optional MCP server | Cursor.app's `python3` must be Python ≥3.10 with `omnicursor[mcp]` and all dependencies installed externally. The launcher prioritizes the copy's `src` |
| MCP node execution | `OMNIMARKET_ROOT` points to the external checkout; the `.git`/`omnimarket-main` development fallback is absent from the payload |
| Bridge subprocesses | `OMNIMARKET_PYTHON`, or the MCP interpreter when unset, must satisfy node dependencies |

`OMNICURSOR_DAEMON_PYTHON` does not select the MCP interpreter. The installer does
not install packages, create environments or rewrite interpreters. Missing `mcp`
produces a stderr diagnostic with the effective interpreter and required extra;
other import errors remain visible. A configured MCP environment can start and
list tools without an OmniMarket checkout; running nodes needs that checkout.

## GUI environment and acceptance

Save your work and fully quit Cursor before setting runtime variables. Launch a
new process through its executable; exports in another terminal, a new window,
or Reload Window do not prove that the application received the environment.
Use externally prepared paths (the MCP PATH entry is needed only for MCP):

```bash
env -u PYTHONPATH -u CLAUDE_CODE_SESSION_ID \
  PATH="/path/to/prepared-mcp/bin:$PATH" \
  OMNICURSOR_DAEMON_PYTHON="/path/to/omnimarket/.venv/bin/python" \
  OMNIMARKET_ROOT="/path/to/omnimarket" \
  OMNIMARKET_PYTHON="/path/to/omnimarket/.venv/bin/python" \
  OMNICURSOR_EMIT_SOCKET="$HOME/.omnicursor/emit.sock" \
  KAFKA_BOOTSTRAP_SERVERS="localhost:19092" \
  /Applications/Cursor.app/Contents/MacOS/Cursor /path/to/foreign-workspace
```

Verify the interpreter and only the relevant variables from the launched process
or a limited probe; do not dump the whole environment. The foreign workspace must
have no OmniCursor project hooks. Record the source revision, installed inventory
and hashes, Cursor version, timestamps and `Plugins.log`. Record rule/skill
discovery and read a skill through an installed rule's relative link. The 17 JSON
files are routing profiles; loading their manifest path does not prove native
agent discovery. Record any agent-folder warnings or plugin rejection verbatim.

Test automatic daemon startup separately with an isolated HOME/socket and external
interpreter. Record the process command and the copied registry path/hash with all
nine keys. Startup is asynchronous: `ensure_daemon()` can return false after spawning,
and the first `session.started` is not retried. A harness invocation is synthetic.
Stop only that test's processes and retain its evidence.

For a real Cursor conversation, make the daemon available **before** sessionStart.
Verify broker connectivity and registry provenance from startup arguments and the
registry hash; ping alone proves only liveness. Create a new conversation, submit
an identifiable prompt with a fictitious credential, and let the turn finish.
Capture sessionStart, prompt and stop for that same conversation: local logs,
`session.started`, canonical prompt and preview, correlated outbox/session outcome,
and B5 `run_id` with `context.toolchain="cursor"`. Stop attribution uses correlation
and B5; it does not require an added `agent_source` field.

Keep four evidence classes separate: synthetic tests, local logs/files, queued
ACKs and records actually read from Kafka (topic, partition, offset and IDs).
Preserve existing user logs. Then test the shim separately with the plugin disabled.
A missing MCP extra means the initialize/tools/list/tool-call test is **SKIPPED,
not verified**; do not install dependencies merely to remove that skip.

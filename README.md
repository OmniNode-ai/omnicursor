# OmniCursor

Cursor-native adaptation of OmniClaude — **rules**, **hooks**, **skills**, and **agent routing** for every workspace you open in Cursor. A Python library under `src/omnicursor/` backs pytest, CI, and the shared logic hooks delegate to; hooks stay stdlib-only at runtime.

## What it does

- **Routes prompts** to the best-matching agent (17 configs, shared scoring engine)
- **Guards shell commands** — hard-blocks dangerous patterns, warns on risky ones
- **Runs diagnostic lint** on Python/TypeScript edits (never auto-fixes)
- **Classifies session outcomes** and writes recaps for the next chat
- **Injects learned patterns** as session context (`sessionStart` / `postToolUse`)
- **Teaches methodology** via 17 file-backed skills (brainstorm → plan → ticket → PR review → handoff)

Works **offline by default**. Optional OmniNode stack integration (pattern sync, Kafka events via the shared emit daemon, OmniMarket nodes) is documented in [ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Requirements

- **Cursor `>= 0.40.0`** (plugin surface; hooks/injection verified on 3.10.11)
- **Python `>= 3.10`** (see `pyproject.toml`; hook scripts themselves run under the system `python3`)
- Supported surface today: the **Cursor IDE**. `cursor-agent` CLI / cloud & background agents are **not verified** — plugin skills, MCP servers, and hooks may not register there.

## Quick start

Install once as a [Cursor plugin](https://cursor.com/docs/plugins):

```bash
git clone https://github.com/OmniNode-ai/OmniCursor ~/tools/OmniCursor
cd ~/tools/OmniCursor
./scripts/install-plugin.sh
```

The installer stages a **curated runtime payload** (rules, hooks, skills, agents, manifest, `src/omnicursor/`, the event-registry config, and docs — never `tests/`, `docker/`, `eval/`, or `.git`) and symlinks it into `~/.cursor/plugins/local/omnicursor`.

Restart Cursor (**Developer: Reload Window**). Confirm rules and skills appear under **Settings → Rules**. `./scripts/install-plugin.sh --status` reports the install state; `--dry-run` previews any action.

Full guide: **[docs/QUICKSTART.md](./docs/QUICKSTART.md)**

## Architecture (four layers)

```
Rules + Skills + Agents     ← behavior surface (.cursor/rules, skills/, .cursor/agents)
        ↓
Hooks (7 lifecycle scripts) ← deterministic, stdlib-only (.cursor/hooks/scripts/)
        ↓
~/.omnicursor/              ← local patterns, events, sessions, outbox (see Privacy)
        ↓
src/omnicursor/             ← shared hook logic, tests, CI, OmniMarket bridge (optional)
```

Deep dive: **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**

## Hooks

Configured in [`.cursor/hooks.json`](./.cursor/hooks.json).

| Hook | Script | What it does |
|------|--------|--------------|
| `sessionStart` | `session-start.py` | Session init, best-effort emit-daemon ensure, **context injection** (baseline patterns + prior session) |
| `beforeSubmitPrompt` | `user-prompt-submit.py` | Agent scoring + canonical event emit for backend learning (block/observe-only — cannot inject) |
| `beforeShellExecution` | `shell-guard.py` | Two-tier command guard (HARD_BLOCK / SOFT_WARN); the only hook that can deny |
| `afterFileEdit` | `post-edit.py` | Diagnostic `ruff check` / `tsc` — does not modify files |
| `postToolUse` | `post-tool-use.py` | **Context refresh** (patterns for the domain inferred from the tool's file path) |
| `stop` | `stop.py` | Session outcome (4-gate), recap, durable outbox write |
| `sessionEnd` | `session-end.py` | Emits the true conversation-close event (fire-and-forget) |

Supporting code lives in `.cursor/hooks/lib/` (`_common.py`, `emit_client.py`, `daemon_ensure.py`, `canonical_event.py`, `redaction.py`, `context_injection.py`). All hook commands use **stdlib only** — no pip dependencies at hook runtime.

### Kill-switch & per-hook mask

- `OMNICURSOR_HOOKS_DISABLE=1` (exact `"1"`) or the marker file `~/.omnicursor/hooks-disabled` disables **all** hooks — they return benign outputs before any side effect (no stdin read, no files written, no emits).
- `OMNICURSOR_HOOKS_MASK="prompt,shell"` enables **only** the named hooks (comma-separated allowlist over `session-start|prompt|shell|edit|tool|stop|session-end`; unset/empty = all enabled).
- A disabled `shell-guard` fails **open** (allow) — the kill-switch turns off side effects, it never blocks you.

## Privacy

**What stays on your machine** — everything under `~/.omnicursor/`:

| Path | Content |
|------|---------|
| `events.jsonl` | Local audit log of hook activity (prompt/command previews are **redacted first**) |
| `learned_patterns.json` | Learned routing patterns (snippets redacted before write) |
| `outbox.jsonl` | Durable session-outcome records |
| `sessions/` | Per-session state used for recaps/injection |
| `emit.sock`, `emit.pid`, `emit-daemon.spawn.stamp` | Shared emit-daemon socket/pid/spawn-dedupe stamp |
| `event-spool/` | Daemon spool for events not yet delivered to Kafka |
| `logs/` | Emit-daemon and spawn logs |
| `hooks-disabled` | Kill-switch marker (created by you) |

**What can leave your machine:** hook events are emitted **best-effort** to a local Unix socket owned by the shared OmniNode emit daemon, which publishes to a Kafka broker at `localhost:19092`. Without that daemon/broker (the default on a standalone install) **nothing is transmitted anywhere** — hooks degrade to local logging only. Before any emit or local write, prompt/command fragments pass through the redaction pass in `.cursor/hooks/lib/redaction.py` (API keys, tokens, passwords, bearer headers, connection strings, private-key blocks, etc.). The full prompt travels only on the restricted `cmd` topic; broadcast events carry a redacted ≤100-char preview.

## Uninstall

```bash
./scripts/install-plugin.sh --uninstall           # removes the plugin; keeps ~/.omnicursor/ data
./scripts/install-plugin.sh --uninstall --purge   # also deletes ~/.omnicursor/ (everything in the table above)
```

`--purge` is opt-in precisely because `~/.omnicursor/` may contain locally learned patterns you want to keep; add `--dry-run` to preview. Purge honors `OMNICURSOR_DATA_DIR` if you relocated the data directory.

## MCP setup (optional — Bucket-3 skills)

The `onex-execute-plan` skill calls the FastMCP bridge server **`omnicursor-omnimarket`**, shipped and registered via [`.cursor/mcp.json`](./.cursor/mcp.json):

```bash
pip install -e ".[mcp]"          # the mcp dependency for the bridge server
export OMNIMARKET_ROOT=/path/to/omnimarket   # local omnimarket checkout
```

The bridge subprocess interpreter can be overridden with `OMNIMARKET_PYTHON`. **Linear MCP is a separate dependency** (already enabled in `.cursor/settings.json`) — `onex-execute-plan` needs both. The registered `python3` must be able to import `omnicursor` and `mcp` (use the venv above, or ensure `PYTHONPATH` covers `src/`).

## Skills (17)

Canonical Markdown in [`skills/`](./skills/), mirrored for Cursor at [`.cursor/skills/onex-<slug>/SKILL.md`](./.cursor/skills/). Each skill id is **`onex-<slug>`** (YAML `name`, `/` picker, compliance registry).

| Bucket | Skills |
|--------|--------|
| **1 — Methodology** | brainstorming, writing-plans, systematic-debugging, pr-review, pr-polish, hostile-reviewer, defense-in-depth, docs-reality-sync, merge-planner, insights-to-plan, plan-review, handoff, recap, using-git-worktrees |
| **2 — Local files** | plan-ticket |
| **3 — External services** | plan-to-tickets, execute-plan (Linear MCP + OmniMarket) |

## Python library

| Module | Role |
|--------|------|
| `scoring.py` / `agents.py` | Agent routing (shared with hooks) |
| `skills.py` | Load skill Markdown |
| `compliance.py` | Keyword rubric checks |
| `session_outbox.py` | Durable local session-outcome record (`~/.omnicursor/outbox.jsonl`) |
| `omnimarket_bridge.py` | Subprocess bridge to local OmniMarket nodes |

Details: [`src/omnicursor/README.md`](./src/omnicursor/README.md)

## Repository layout

```text
OmniCursor/
├── .cursor-plugin/plugin.json   # Cursor plugin manifest (single canonical)
├── .cursor/
│   ├── rules/                   # 14 .mdc rules (4 always-on)
│   ├── hooks/                   # 7 hook scripts + lib/
│   ├── hooks.json
│   ├── mcp.json                 # omnicursor-omnimarket bridge registration
│   ├── skills/                  # onex-*/SKILL.md mirrors
│   └── agents/                  # 17 JSON routing configs
├── config/event_registry/       # Emit-daemon fan-out registry (semantic key → topics)
├── docs/                        # QUICKSTART, ARCHITECTURE
├── provisioning/                # Optional launchd/systemd templates for the emit daemon
├── skills/                      # Canonical skill Markdown
├── src/omnicursor/              # Python library + node contracts
├── tests/
├── scripts/install-plugin.sh
├── CHANGELOG.md
├── LICENSE
└── pyproject.toml
```

## Developer setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
pytest tests/ -v
ruff check src/ tests/ .cursor/hooks/
```

The tracked pre-commit hook runs the same checks as CI (`ruff`, `pytest`, skill compliance). Use `git commit --no-verify` only for emergency bypasses.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/QUICKSTART.md](./docs/QUICKSTART.md) | Install, hooks, skills, Linear MCP, privacy |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Layers, buckets, routing, intelligence A/B/C |
| [docs/README.md](./docs/README.md) | Documentation map |
| [CHANGELOG.md](./CHANGELOG.md) | Release history (Keep a Changelog) |

Directory guides: `.cursor/`, `docs/`, `skills/`, `src/omnicursor/`, `tests/` each have a `README.md`.

# OmniCursor Quickstart

OmniCursor is a [Cursor plugin](https://cursor.com/docs/plugins): agent routing, shell guards, session recaps, and 17 methodology skills. Install it once on your machine; it applies to every project you open in Cursor.

---

## Requirements

- [Cursor](https://cursor.com) (recent version with plugin support)
- Python 3.10+ on your PATH (hooks invoke `python3`; stdlib only)

---

## Step 1 — Clone to a permanent location

```bash
git clone https://github.com/OmniNode-ai/OmniCursor ~/tools/OmniCursor
cd ~/tools/OmniCursor
```

## Step 2 — Install the plugin

```bash
./scripts/install-plugin.sh
```

This symlinks the repo to `~/.cursor/plugins/local/omnicursor`. Equivalent manual step:

```bash
mkdir -p ~/.cursor/plugins/local
ln -sfn ~/tools/OmniCursor ~/.cursor/plugins/local/omnicursor
```

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

### Hooks (automatic, no trigger needed)

| Hook | When it fires | What it does |
|------|--------------|--------------|
| `beforeSubmitPrompt` | Every prompt | Routes your prompt to the best agent, injects routing context and learned patterns |
| `beforeShellExecution` | Every shell command | Blocks dangerous commands (e.g. `rm -rf /`, `--no-verify`), warns on risky ones |
| `afterFileEdit` | Every file save | Runs `ruff check` diagnostically on Python files |
| `stop` | Session end | Classifies session outcome (success / failed / abandoned), writes recap for next session |

### Skills (keyword-triggered)

Say the keyword in chat and Cursor reads the skill file and follows it.

**Slash menu (`/`):** Each skill uses YAML frontmatter with `name: onex-<slug>`. Typing `/` shows those ids (e.g. `onex-brainstorming`).

| Keyword | Skill | What it does |
|---------|-------|--------------|
| `recap` or `/recap` | onex-recap | Summarizes the current session inline; auto-injects previous session recap at start |
| `brainstorm` | onex-brainstorming | Structured ideation with diverge → converge flow |
| `debug` / `root cause` | onex-systematic-debugging | 5-phase root cause analysis — no guessing |
| `write a plan` | onex-writing-plans | Implementation plan with TDD tasks and acceptance criteria |
| `create ticket` | onex-plan-ticket | Converts a plan task into a structured Linear ticket |
| `pr review` | onex-pr-review | Severity-classified PR review (CRITICAL / MAJOR / MINOR / NIT) |
| `handoff` | onex-handoff | Session summary for the next chat |

See [`skills/`](../skills/) and [`.cursor/skills/`](../.cursor/skills/) for the full set.

### Rules (always-on + keyword)

Four rules in `.cursor/rules/` are always active (`00`–`03`). Ten others activate on keywords (brainstorm, plan, debug, PR review, handoff, recap, Linear tickets, execute-plan, etc.). See [`.cursor/rules/README.md`](../.cursor/rules/README.md).

---

## Optional: Linear MCP (Bucket 3 skills)

Skills like `onex-plan-to-tickets` and `onex-execute-plan` need the Linear MCP server.

**1. Get a Linear API key** — Linear → Settings → API → Personal API keys.

**2. Add to `~/.cursor/mcp.json`:**

```json
{
  "mcpServers": {
    "linear": {
      "command": "npx",
      "args": ["-y", "@linear/mcp-server"],
      "env": {
        "LINEAR_API_KEY": "lin_api_XXXX"
      }
    }
  }
}
```

Replace `lin_api_XXXX` with your actual key.

**3. Restart Cursor** — the `tracker.*` MCP tools become available in chat.

**4. Verify** — open a Cursor chat and say "list my Linear teams". It should return your teams.

---

## Updating OmniCursor

```bash
cd ~/tools/OmniCursor && git pull
```

Reload Cursor if rules or hooks do not pick up changes immediately.

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
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
pytest tests/ -v
ruff check src/ tests/ .cursor/hooks/
```

CI runs the same checks on every PR to `main`.

## Privacy — what OmniCursor stores locally

OmniCursor writes session data to two files under `~/.omnicursor/`:

**`~/.omnicursor/events.jsonl`** — structured log of every hook event (prompt classifications, shell guard decisions, edit lint results, session outcomes). Contains the prompt text that was submitted to the router and the agent/confidence result.

**`~/.omnicursor/learned_patterns.json`** — the pattern learning cache. Each record stores:
- `key`: a sorted keyword fingerprint extracted from the prompt (e.g. `"debug fix test TypeError"`) — not the full prompt
- `description`: `"Auto-learned: <first 60 chars of prompt> → <agent> (score X.XX)"` — captures up to 60 characters of prompt content
- `domain`, `weight`, `success_count`, `injection_count`, `utilization_successes`, `last_seen`

**The description field captures prompt content.** If your prompts contain secrets, credentials, PII, or sensitive project names, that content may appear in `learned_patterns.json`. OmniCursor does not transmit this file anywhere — it is read-only local storage unless you explicitly enable `OMNICURSOR_PATTERN_SYNC_HTTP=1` (off by default), which pulls updated patterns from a local intelligence-reducer service (`http://127.0.0.1:18091`) but does not upload your local file. If the service is offline, the local file is left unchanged.

If you are working with sensitive material, avoid typing it directly into prompts or clear `~/.omnicursor/learned_patterns.json` periodically.

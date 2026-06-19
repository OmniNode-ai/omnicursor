# OmniCursor Quickstart

OmniCursor is a [Cursor plugin](https://cursor.com/docs/plugins): agent routing, shell guards, session recaps, and 17 methodology skills. Install it once on your machine; it applies to **every project** you open in Cursor.

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

### Hooks (automatic)

| Hook | When it fires | What it does |
|------|--------------|--------------|
| `beforeSubmitPrompt` | Every prompt | Routes to the best agent, injects learned patterns and persona via `systemMessage` |
| `beforeShellExecution` | Every shell command | Blocks dangerous commands (e.g. `rm -rf /`, `--no-verify`), warns on risky ones |
| `afterFileEdit` | Every file save | Runs `ruff check` / `tsc` diagnostically on edited files |
| `stop` | Session end | Classifies session outcome (success / failed / abandoned), writes recap for next session |

Only **shell-guard** can block execution. All other hooks always exit 0.

### Rules (always-on + keyword)

Four rules are **always active** (`00`–`03`): ONEX vocabulary, codebase research policy, no-secrets guard, and OmniCursor/OmniMarket ownership boundary.

Ten others activate on keywords (brainstorm, plan, debug, PR review, handoff, recap, Linear tickets, execute-plan, etc.). See [`.cursor/rules/README.md`](../.cursor/rules/README.md).

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

#### Bucket 2 — Local files

| Keyword | Skill | What it does |
|---------|-------|--------------|
| `create ticket` | onex-plan-ticket | Converts a plan task into a structured YAML ticket template |

#### Bucket 3 — External services

| Keyword | Skill | Requires | What it does |
|---------|-------|----------|--------------|
| `plan to tickets` | onex-plan-to-tickets | Linear MCP | Batch-create Linear tickets from a plan |
| `execute plan` | onex-execute-plan | Linear MCP (+ OmniMarket for node dispatch) | Autonomous ticket execution pipeline |

See [`.cursor/skills/`](../.cursor/skills/) for the full set. Architecture details: [ARCHITECTURE.md](./ARCHITECTURE.md).

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

## Optional: OmniNode stack (patterns + events)

OmniCursor works fully offline with local pattern learning (`~/.omnicursor/learned_patterns.json`). To connect to the wider OmniNode stack:

1. Copy [`.env.omninode.example`](../.env.omninode.example) and set `OMNIMARKET_ROOT`, `INTELLIGENCE_SERVICE_URL`, etc.
2. Start local services: `docker compose up -d` (Redpanda, omniintelligence)
3. Enable HTTP pattern sync: `OMNICURSOR_PATTERN_SYNC_HTTP=1`
4. For event publishing: `bash scripts/run_sidecar.sh --publisher kafka`

See [ARCHITECTURE.md](./ARCHITECTURE.md) § Intelligence options for the A/B/C model.

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

Key contributor docs:

- [ARCHITECTURE.md](./ARCHITECTURE.md) — layers, buckets, routing, sidecar
- [HANDOFF.md](./HANDOFF.md) — onboarding path and common tasks
- [README.md](./README.md) — documentation map

---

## Privacy — what OmniCursor stores locally

OmniCursor writes session data to files under `~/.omnicursor/`:

**`events.jsonl`** — structured log of every hook event (prompt classifications, shell guard decisions, edit lint results, session outcomes). Contains the prompt text submitted to the router and the agent/confidence result.

**`learned_patterns.json`** — the pattern learning cache. Each record stores:

- `key`: a sorted keyword fingerprint extracted from the prompt (e.g. `"debug fix test TypeError"`) — not the full prompt
- `description`: `"Auto-learned: <first 60 chars of prompt> → <agent> (score X.XX)"` — captures up to 60 characters of prompt content
- `domain`, `weight`, `success_count`, `injection_count`, `utilization_successes`, `last_seen`

**The description field captures prompt content.** If your prompts contain secrets, credentials, PII, or sensitive project names, that content may appear in `learned_patterns.json`. OmniCursor does not transmit this file anywhere by default — it is local storage unless you enable `OMNICURSOR_PATTERN_SYNC_HTTP=1` (pull-only from a local omniintelligence service) or run the Option C sidecar with Kafka publishing.

If you are working with sensitive material, avoid typing it directly into prompts or clear `~/.omnicursor/learned_patterns.json` periodically.

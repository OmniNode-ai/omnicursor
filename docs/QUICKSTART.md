# OmniCursor Quickstart

OmniCursor is a Cursor plugin that adds agent routing, shell guards, session recaps, and 17 methodology skills to any project. Clone it once to a permanent location, then install it into as many projects as you want.

---

## Requirements

- [Cursor](https://cursor.com) (any recent version)
- Python 3.10 or newer

---

## Step 1 — Clone to a permanent location

Pick somewhere you won't delete it. The plugin lives here permanently; your projects symlink back to it.

```bash
git clone https://github.com/OmniNode-ai/OmniCursor ~/tools/OmniCursor
cd ~/tools/OmniCursor
```

## Step 2 — Install the Python package

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## Step 3 — Install into your project

Run this once for each project you want OmniCursor on:

```bash
~/tools/OmniCursor/install.sh /path/to/your-project
```

This creates symlinks in your project's `.cursor/` and `skills/` directories pointing back to OmniCursor. No files are copied — updating OmniCursor (`git pull`) automatically updates every installed project.

> **Note:** Cursor hooks and rules are per-project. There is no global Cursor plugin system, so this one-time install step per project is unavoidable.

**Check what was installed:**

```bash
~/tools/OmniCursor/install.sh /path/to/your-project --status
```

## Step 4 — Open your project in Cursor

Restart Cursor (or reload the window with `Ctrl+Shift+P → Reload Window`) to activate hooks and rules.

That's it — OmniCursor is running.

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

**Slash menu (`/`):** Each skill file uses Cursor Agent Skills YAML frontmatter. The `name` field matches the canonical id (`onex:<slug>` — for example `onex:brainstorming`). Typing `/` in chat shows those names so the picker aligns with OmniCursor hooks and docs that reference the `onex:` namespace.

| Keyword | Skill | What it does |
|---------|-------|--------------|
| `recap` or `/recap` | onex:recap | Summarizes the current session inline; auto-injects previous session recap at start |
| `brainstorm` | onex:brainstorming | Structured ideation with diverge → converge flow |
| `debug` / `root cause` | onex:systematic-debugging | 5-phase root cause analysis — no guessing |
| `write a plan` | onex:writing-plans | Implementation plan with TDD tasks and acceptance criteria |
| `create ticket` | onex:plan-ticket | Converts a plan task into a structured Linear ticket |
| `review this PR` | onex:pr-review | Structured PR review with severity classification |
| `polish this PR` | onex:pr-polish | Pre-merge checklist: description, diff, CI, changelog |
| `hostile review` | onex:hostile-reviewer | Adversarial multi-pass review — finds what polite review misses |
| `defense in depth` | onex:defense-in-depth | Adds validation layers at system boundaries |
| `docs drift` / `reality sync` | onex:docs-reality-sync | Inventory docs vs code; fix or archive drift |
| `merge plan` | onex:merge-planner | Safe merge sequencing for complex branch stacks |
| `insights to plan` | onex:insights-to-plan | Converts retrospective notes into actionable tasks |
| `handoff` | onex:handoff | Saves session context so the next session picks up cleanly |
| `worktree` | onex:using-git-worktrees | Isolated branch workspaces without stashing |
| `/plan-review` | onex:plan-review | Adversarial R1–R6 check on a plan file before execution |
| `/plan-to-tickets` | onex:plan-to-tickets | Parse a plan file and batch-create Linear tickets |
| `/execute_plan` | onex:execute-plan | Full autonomous pipeline: review → tickets → implement |

---

## Linear MCP Setup (for plan-to-tickets and execute_plan)

`plan-to-tickets` and `execute_plan` create tickets in Linear via MCP. Skip this section if you don't use Linear.

**1. Get your Linear API key**

Linear → Settings → API → Personal API Keys → Create key.

**2. Edit `~/.cursor/mcp.json`** (create the file if it doesn't exist):

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

Because install uses symlinks, a `git pull` updates all installed projects immediately — no reinstall needed.

```bash
cd ~/tools/OmniCursor && git pull
```

## Removing from a project

```bash
~/tools/OmniCursor/install.sh /path/to/your-project --uninstall
```

Removes the symlinks. Your project's other `.cursor/rules/` and `skills/` files are left intact.

---

## Developer setup (contributing to OmniCursor)

```bash
cd ~/tools/OmniCursor
source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
pytest tests/ -v
ruff check src/ tests/ .cursor/hooks/
```

CI runs the same checks on every PR to `main`.

---

## Privacy — what OmniCursor stores locally

OmniCursor writes session data to two files under `~/.omnicursor/`:

**`~/.omnicursor/events.jsonl`** — structured log of every hook event (prompt classifications, shell guard decisions, edit lint results, session outcomes). Contains the prompt text that was submitted to the router and the agent/confidence result.

**`~/.omnicursor/learned_patterns.json`** — the pattern learning cache. Each record stores:
- `key`: a sorted keyword fingerprint extracted from the prompt (e.g. `"debug fix test TypeError"`) — not the full prompt
- `description`: `"Auto-learned: <first 60 chars of prompt> → <agent> (score X.XX)"` — captures up to 60 characters of prompt content
- `domain`, `weight`, `success_count`, `injection_count`, `utilization_successes`, `last_seen`

**The description field captures prompt content.** If your prompts contain secrets, credentials, PII, or sensitive project names, that content may appear in `learned_patterns.json`. OmniCursor does not transmit this file anywhere — it is read-only local storage unless you explicitly enable `OMNICURSOR_PATTERN_SYNC_HTTP=1` (off by default), which pulls updated patterns from a local intelligence-reducer service (`http://127.0.0.1:18091`) but does not upload your local file. If the service is offline, the local file is left unchanged.

If you are working with sensitive material, avoid typing it directly into prompts or clear `~/.omnicursor/learned_patterns.json` periodically.

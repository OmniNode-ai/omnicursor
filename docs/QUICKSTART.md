# OmniCursor Quickstart

OmniCursor is a Cursor plugin that adds agent routing, shell guards, session recaps, and 13 methodology skills to any project. Clone it once to a permanent location, then install it into as many projects as you want.

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

| Keyword | Skill | What it does |
|---------|-------|--------------|
| `recap` or `/recap` | recap | Summarizes the current session inline; auto-injects previous session recap at start |
| `brainstorm` | brainstorming | Structured ideation with diverge → converge flow |
| `debug` / `root cause` | systematic-debugging | 5-phase root cause analysis — no guessing |
| `write a plan` | writing-plans | Implementation plan with TDD tasks and acceptance criteria |
| `create ticket` | plan-ticket | Converts a plan task into a structured Linear ticket |
| `review this PR` | pr-review | Structured PR review with severity classification |
| `polish this PR` | pr-polish | Pre-merge checklist: description, diff, CI, changelog |
| `hostile review` | hostile-reviewer | Adversarial multi-pass review — finds what polite review misses |
| `defense in depth` | defense-in-depth | Adds validation layers at system boundaries |
| `merge plan` | merge-planner | Safe merge sequencing for complex branch stacks |
| `insights to plan` | insights-to-plan | Converts retrospective notes into actionable tasks |
| `handoff` | handoff | Saves session context so the next session picks up cleanly |
| `worktree` | using-git-worktrees | Isolated branch workspaces without stashing |
| `/plan-review` | plan-review | Adversarial R1–R6 check on a plan file before execution |
| `/plan-to-tickets` | plan-to-tickets | Parse a plan file and batch-create Linear tickets |
| `/execute_plan` | execute-plan | Full autonomous pipeline: review → tickets → implement |

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

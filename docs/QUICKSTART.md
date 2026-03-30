# OmniCursor Quickstart

This repository now has two layers:

1. The preserved Cursor starter kit in [`.cursor/rules`](../.cursor/rules), [`docs`](../docs), and [`tests`](../tests)
2. The OmniCursor MCP backend in [`src/omnicursor`](../src/omnicursor) and [`skills`](../skills)

## Prerequisites

- Python 3.10 or newer
- A virtual environment for this repo

The official MCP Python SDK currently requires Python 3.10+.

## Install

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run the MCP server

```bash
source .venv/bin/activate
omnicursor-server
```

The default transport is `stdio`, which is the right starting point for a local Cursor MCP server.

## Use in Cursor

1. Open the repository root, not a parent folder.
2. Confirm the preserved rules under [`.cursor/rules`](../.cursor/rules) are visible in Cursor.
3. Register a local MCP server command that runs `omnicursor-server` from this repo's virtual environment.
4. Use the preserved rules for brainstorming, planning, ticketing, and adapter behavior.
5. The MCP tools enhance each rule with routing, skill loading, and compliance checking.

## Available MCP Tools

### `get_agent_context(category: str)`

Returns routing context (agent name, instructions, recommended skill) for a given category.

| Category | Agent | Matching Rule | Recommended Skill |
|----------|-------|---------------|-------------------|
| `debugging` | systematic-debugger | 10-systematic-debugging.mdc | systematic-debugging |
| `brainstorming` | brainstorming-guide | 10-brainstorming.mdc | brainstorming |
| `planning` | plan-writer | 11-writing-plans.mdc | writing-plans |
| `ticketing` | ticket-planner | 12-plan-ticket.mdc | plan-ticket |
| `adapter` | adapter-guide | 20-adapter-stub.mdc | adapter-stub |

Unrecognized categories fall back to `omnicursor-generalist`.

### `invoke_skill(skill_name: str)`

Loads a Markdown skill from the `skills/` directory and returns its content.

### `check_compliance(skill_name: str, response_summary: str)`

Checks whether a model response complies with a skill's expected output pattern. Returns a checklist with pass/fail for each expected element.

## Available Skills

| Skill | File | Purpose |
|-------|------|---------|
| `systematic-debugging` | `skills/systematic-debugging.md` | Structured debugging: reproduce, hypothesize, verify |
| `brainstorming` | `skills/brainstorming.md` | Refine ideas into validated design docs |
| `writing-plans` | `skills/writing-plans.md` | Design docs into TDD implementation plans |
| `plan-ticket` | `skills/plan-ticket.md` | Plans into YAML ticket contract templates |
| `adapter-stub` | `skills/adapter-stub.md` | Bucket 3 dry-run stubs with fail-soft behavior |

## End-to-End Flow in Cursor

A typical session using all three MCP tools:

1. **User invokes `@10-brainstorming` with an idea.**
   - Rule calls `get_agent_context("brainstorming")` for routing context.
   - Rule calls `invoke_skill("brainstorming")` for the full methodology.
   - Collaborative dialogue refines the idea into a design doc.
   - Rule calls `check_compliance("brainstorming", summary)` to verify output quality.
   - Design saved to `docs/plans/YYYY-MM-DD-<topic>-design.md`.

2. **User invokes `@11-writing-plans` with the design doc path.**
   - Rule calls `get_agent_context("planning")` for routing context.
   - Design is broken into bite-sized TDD tasks with adversarial review.
   - Rule calls `check_compliance("writing-plans", summary)` to verify.
   - Plan saved to `docs/plans/YYYY-MM-DD-<feature>.md`.

3. **User invokes `@12-plan-ticket` with the plan path.**
   - Rule calls `get_agent_context("ticketing")` for routing context.
   - Deterministic repo detection runs. YAML ticket template generated.
   - Rule calls `check_compliance("plan-ticket", summary)` to verify.

4. **(Stage 2) User invokes `@20-adapter-stub` for external integration.**
   - Rule calls `get_agent_context("adapter")` for routing context.
   - Dry-run payload constructed. Fail-soft behavior enforced.

## Hooks

Cursor hooks are deterministic Python scripts that fire on editor lifecycle events. They are **not** interpreted by the LLM — they run as subprocesses before or after specific actions. No pip dependencies required (stdlib only).

### Configuration

`.cursor/hooks.json` controls which scripts run and when. To disable all hooks, rename it to `.cursor/hooks.json.disabled`.

### Active Hooks

**`beforeSubmitPrompt` → `on_prompt.py`** — Classifies each prompt against the 16 agent configs in `.cursor/agents/` using trigger-based scoring (`explicit_triggers` = 2 pts, `context_triggers` = 1 pt). The matched agent and score are logged to `~/.omnicursor/events.jsonl`. This hook is informational only — it cannot modify the prompt.

**`beforeShellExecution` → `on_shell.py`** — Guards against dangerous shell commands using a two-tier regex system. Hard-blocked commands (e.g., `rm -rf /`, `--no-verify`, fork bombs) are denied outright. Risky commands (e.g., `git push --force`, `DROP TABLE`, `curl | sh`) are allowed with a warning injected into the agent context.

**`afterFileEdit` → `on_edit.py`** — Logs every file edit with language detection and edit count. For Python files, runs `ruff check` (diagnostic only, never `--fix`) and logs any issues to `~/.omnicursor/lint.jsonl`.

**`stop` → `on_stop.py`** — Aggregates all events for the ending conversation: prompt classifications, unique files edited, shell command decisions, and languages used. Writes a session summary to `~/.omnicursor/sessions/<conversation_id>.json`.

### Verifying Hooks Work

- **Event log**: `cat ~/.omnicursor/events.jsonl` — one JSON line per event
- **Session summaries**: `ls ~/.omnicursor/sessions/` — one file per completed conversation
- **Cursor UI**: Open Output channels → Hooks to see real-time stdout/stderr from hook scripts

### Requirements

- Python 3.10+ (same as the MCP server)
- `ruff` (optional) — if installed, `on_edit.py` runs diagnostic linting on Python files

### Phase 3B Preview

Two additional hooks are planned:
- `beforeMCPExecution` — intercept and validate MCP tool calls before they execute
- `beforeReadFile` — control file access patterns and log read operations

## Notes

- [`HOW_TO_RUN_IN_CURSOR.md`](../HOW_TO_RUN_IN_CURSOR.md) is preserved as the original starter-kit walkthrough.
- [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) remains the bucket and adapter contract reference.

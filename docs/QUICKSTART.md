# OmniCursor Quickstart

OmniCursor has **three layers** — rules and hooks in the IDE, plus a **Python library** for tests and automation:

1. **Cursor Rules** (`.cursor/rules/`, 11 `.mdc` files) — behavior surface
2. **Cursor Hooks** (`.cursor/hooks/`) — 4 hook entrypoints in `.cursor/hooks.json`, plus `_common.py` and `pattern_loader.py`. Deterministic, stdlib only, no LLM
3. **Python library** (`src/omnicursor/`) — `get_agent_context`, skill loading, `check_compliance` — use from tests, CI, or one-off `python -c` snippets

## Prerequisites

- Python 3.10 or newer (developed on 3.12)
- A virtual environment for this repo

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

## Local Pre-Commit Checks

This repo includes a tracked git pre-commit hook in `.githooks/pre-commit`.

- It runs `ruff check src/ tests/ .cursor/hooks/`.
- It runs `pytest tests/ -v`.
- It validates skill compliance coverage using the **same rule as CI** (every `skills/*.md` has a `compliance.py` entry).
- GitHub Actions CI runs on pull requests to `main`.

Use `git commit --no-verify` only for emergency bypasses.

## Use in Cursor

1. Open the repository root, not a parent folder.
2. Confirm the rules under `.cursor/rules/` are visible in Cursor Settings.
3. Hooks are active via `.cursor/hooks.json` — no extra configuration.
4. Use `@`-rules for brainstorming, planning, ticketing, debugging, PR review, handoff, etc.
5. The model loads skills by reading **`.cursor/skills/<name>/SKILL.md`** (see table below). Hook output may include routing hints in `systemMessage` (`beforeSubmitPrompt`).

## Structured API (Python library)

For structured payloads in code or tests:

### `get_agent_context(category: str)`

Returns routing context (`AgentContext` — agent name, instructions, recommended skill). Used in tests; rules typically rely on hooks + reading `.cursor/skills/<name>/SKILL.md`.

| Category | Agent | Matching Rule | Recommended Skill |
|----------|-------|---------------|-------------------|
| `debugging` | systematic-debugger | 13-systematic-debugging.mdc | systematic-debugging |
| `brainstorming` | brainstorming-guide | 10-brainstorming.mdc | brainstorming |
| `planning` | plan-writer | 11-writing-plans.mdc | writing-plans |
| `ticketing` | ticket-planner | 12-plan-ticket.mdc | plan-ticket |
| `review` | pr-review | 14-pr-review.mdc | pr-review |
| `handoff` | handoff-guide | 15-handoff.mdc | handoff |

Unrecognized categories fall back to `omnicursor-generalist`.

Example:

```bash
python -c "from omnicursor.agents import get_agent_context; import json; print(json.dumps(get_agent_context('debugging').model_dump(), indent=2))"
```

### Skills on disk

Read `.cursor/skills/<skill_name>/SKILL.md` from the repo root, or use `SkillRepository` in Python / tests.

### `check_compliance(skill_name, response_summary)`

Implemented in `src/omnicursor/compliance.py`. Run via `pytest tests/test_compliance.py` or call from Python.

## Available Skills (12)

| Skill | File | Purpose |
|-------|------|---------|
| `systematic-debugging` | `.cursor/skills/systematic-debugging/SKILL.md` | Structured debugging |
| `brainstorming` | `.cursor/skills/brainstorming/SKILL.md` | Design exploration |
| `writing-plans` | `.cursor/skills/writing-plans/SKILL.md` | TDD-oriented plans |
| `plan-ticket` | `.cursor/skills/plan-ticket/SKILL.md` | YAML ticket templates |
| `pr-review` | `.cursor/skills/pr-review/SKILL.md` | PR review methodology |
| `pr-polish` | `.cursor/skills/pr-polish/SKILL.md` | PR refinement |
| `hostile-reviewer` | `.cursor/skills/hostile-reviewer/SKILL.md` | Adversarial multi-pass review |
| `defense-in-depth` | `.cursor/skills/defense-in-depth/SKILL.md` | Data-flow validation |
| `merge-planner` | `.cursor/skills/merge-planner/SKILL.md` | Merge planning |
| `insights-to-plan` | `.cursor/skills/insights-to-plan/SKILL.md` | Findings → plan |
| `handoff` | `.cursor/skills/handoff/SKILL.md` | Session handoff |
| `using-git-worktrees` | `.cursor/skills/using-git-worktrees/SKILL.md` | Worktree workflow |

## End-to-End Flow in Cursor

1. **User invokes `@10-brainstorming`.**
   - Hook may classify the prompt and inject `systemMessage`.
   - Model reads `.cursor/skills/brainstorming/SKILL.md` and follows the methodology.
   - Design saved to `docs/plans/YYYY-MM-DD-<topic>-design.md`.

2. **User invokes `@11-writing-plans`** with the design path.
   - Model reads `.cursor/skills/writing-plans/SKILL.md`.
   - Plan saved under `docs/plans/`.

3. **User invokes `@12-plan-ticket`** with the plan path.
   - Model reads `.cursor/skills/plan-ticket/SKILL.md`; repo detection per rule.

**Other external systems (Kafka, full ONEX runtime):** out of scope — see `docs/ARCHITECTURE.md`.

## Hooks

Cursor hooks are deterministic Python scripts. No pip dependencies in hook code (stdlib only).

### Configuration

`.cursor/hooks.json` — rename to disable all hooks: `hooks.json.disabled`.

### Active Hooks

**`beforeSubmitPrompt` → `on_prompt.py`** — Classifies each prompt against agent configs (three-strategy scoring). `HARD_FLOOR = 0.55`. Emits `{"systemMessage": ...}` with agent, confidence, learned patterns from `~/.omnicursor/learned_patterns.json`.

**`beforeShellExecution` → `on_shell.py`** — Hard-block and soft-warn regex tiers.

**`afterFileEdit` → `on_edit.py`** — Logs edits; diagnostic `ruff check` on Python.

**`stop` → `on_stop.py`** — Session outcome (4-gate) and `~/.omnicursor/sessions/`.

### Verifying Hooks

```bash
echo '{"prompt": "help me debug this error"}' | python3 .cursor/hooks/on_prompt.py
echo '{"command": "rm -rf /"}' | python3 .cursor/hooks/on_shell.py
echo '{"conversation_id": "test-123", "status": "completed"}' | python3 .cursor/hooks/on_stop.py
```

- Event log: `~/.omnicursor/events.jsonl`
- Session summaries: `~/.omnicursor/sessions/`

### Requirements

- Python 3.10+ for hooks
- `ruff` (optional) for `on_edit.py` diagnostics

## Notes

- [`docs/dev/HOW_TO_RUN_IN_CURSOR.md`](./dev/HOW_TO_RUN_IN_CURSOR.md) — historical starter walkthrough
- [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) — bucket model and adapter contract

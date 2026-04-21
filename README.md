# OmniCursor

Cursor-native adaptation of OmniClaude — **rules**, **hooks**, and **file-backed skills** (Markdown), plus a Python library for tests and CI.

## Architecture

1. **Cursor Rules** (11 `.mdc` files in `.cursor/rules/`) — behavior surface; always-on + keyword-activated
2. **Cursor Hooks** (`.cursor/hooks/`) — 4 hook entrypoints in `.cursor/hooks.json`, plus `_common.py` and `pattern_loader.py`. Deterministic, stdlib only, no LLM
3. **Python library** (`src/omnicursor/`) — `agents`, `skills`, `compliance`, node contracts — for **pytest**, scripting, and rubric checks

## Quick Start

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
pytest tests/ -v
```

See [`docs/QUICKSTART.md`](./docs/QUICKSTART.md) for Cursor setup, hooks, and end-to-end flow.

## Git Pre-Commit Gate

This repo ships a tracked pre-commit hook at `.githooks/pre-commit`.

- It runs CI-parity checks locally before each commit: `ruff`, `pytest`, and skill compliance coverage.
- Enable it once per clone with `git config core.hooksPath .githooks`.
- Use `git commit --no-verify` only for emergency bypasses.
- GitHub Actions CI runs on pull requests to `main`; local pre-commit checks are the first line of defense before opening a PR.

## Hooks

Deterministic Python scripts on Cursor lifecycle events. Configured in `.cursor/hooks.json`.

| Hook | Script | What it does |
|------|--------|--------------|
| `beforeSubmitPrompt` | `on_prompt.py` | Three-strategy agent scoring, emits `{"systemMessage": ...}` with agent + confidence + learned patterns |
| `beforeShellExecution` | `on_shell.py` | Two-tier command guard: HARD_BLOCK (deny), SOFT_WARN (allow + warning) |
| `afterFileEdit` | `on_edit.py` | Logs edits, runs diagnostic `ruff check` on Python files |
| `stop` | `on_stop.py` | Session outcome classification (4-gate) and summaries |

Supporting modules: `_common.py`, `pattern_loader.py`. All hooks use stdlib only.

## Python library (tests & CI)

| Concern | Module |
|---------|--------|
| Category → routing context | `omnicursor.agents.get_agent_context` |
| Load `skills/*.md` | `omnicursor.skills.SkillRepository` |
| Keyword compliance checks | `omnicursor.compliance.check_compliance` |

## Agent Configs

17 JSON configs in [`.cursor/agents/`](./.cursor/agents/) define activation patterns for prompt-based routing. Hooks (`on_prompt.py`) and `agents.py` use the same three-strategy scoring (`HARD_FLOOR = 0.55`).

## Skills

14 Markdown skills in [`skills/`](./skills/): methodology documents the model reads from disk (paths in each rule / QUICKSTART). Each skill has a compliance registry entry in `src/omnicursor/compliance.py`.

## Directory guides

Major folders include **`README.md`** (e.g. `.cursor/`, `docs/`, `skills/`, `src/omnicursor/`, `tests/`).

## Repository Layout

```text
OmniCursor/
├── .cursor/
│   ├── rules/              # Cursor rules (.mdc)
│   ├── hooks/              # Hook scripts + helpers
│   ├── hooks.json
│   └── agents/             # Agent JSON configs
├── docs/
├── skills/                 # Markdown skills
├── src/omnicursor/         # Python library
├── tests/
├── omniclaude-main/        # Read-only OmniClaude reference
├── pyproject.toml
└── CLAUDE.md
```

## Tests

```bash
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
pytest tests/ -v
ruff check src/ tests/ .cursor/hooks/
```

## Documentation

- [`CLAUDE.md`](./CLAUDE.md) — Conventions and architecture
- [`docs/QUICKSTART.md`](./docs/QUICKSTART.md) — Setup, hooks, skills
- [`docs/dev/HANDOFF.md`](./docs/dev/HANDOFF.md) — Implementation state
- [`OmniCursor_DoD_Rubric.md`](./OmniCursor_DoD_Rubric.md) — Capstone rubric
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — Starter-pack buckets / adapter contract

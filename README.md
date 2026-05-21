# OmniCursor

Cursor-native adaptation of OmniClaude — **rules**, **hooks**, and **file-backed skills** (Markdown), plus a Python library for tests and CI.

## Architecture

1. **Cursor Rules** (14 `.mdc` files in `.cursor/rules/`) — behavior surface; always-on + keyword-activated
2. **Cursor Hooks** (`.cursor/hooks/`) — 4 hook entrypoints in `.cursor/hooks.json`, commands under `.cursor/hooks/scripts/`, plus helpers in `hooks/lib/`, `_common.py`, and `pattern_loader.py`. Deterministic, stdlib only, no LLM
3. **Python library** (`src/omnicursor/`) — `agents`, `skills`, `compliance`, node contracts — for **pytest**, scripting, and rubric checks

## Quick Start

Install once as a [Cursor plugin](https://cursor.com/docs/plugins). Rules, skills, agents, and hooks then apply to **every** workspace you open.

```bash
git clone https://github.com/OmniNode-ai/OmniCursor ~/tools/OmniCursor
cd ~/tools/OmniCursor
./scripts/install-plugin.sh
```

Restart Cursor (or **Developer: Reload Window**). Check **Settings → Rules** for OmniCursor rules and skills.

Manifest: [`.cursor-plugin/plugin.json`](./.cursor-plugin/plugin.json). Full guide: **[`docs/QUICKSTART.md`](./docs/QUICKSTART.md)**.

## Git Pre-Commit Gate

This repo ships a tracked pre-commit hook at `.githooks/pre-commit`.

- It runs the **same checks as CI** locally before each commit: `ruff`, `pytest`, and skill compliance coverage.
- Enable it once per clone with `git config core.hooksPath .githooks`.
- Use `git commit --no-verify` only for emergency bypasses.
- GitHub Actions CI runs on pull requests to `main`; local pre-commit checks are the first line of defense before opening a PR.

## Hooks

Deterministic Python scripts on Cursor lifecycle events. Configured in `.cursor/hooks.json`.

| Hook | Script (see `.cursor/hooks.json`) | What it does |
|------|--------|--------------|
| `beforeSubmitPrompt` | `.cursor/hooks/scripts/user-prompt-submit.py` | Multi-strategy agent scoring; injects learned patterns + agent persona into the prompt (`systemMessage` / routing hooks output) |
| `beforeShellExecution` | `.cursor/hooks/scripts/shell-guard.py` | Two-tier command guard: HARD_BLOCK (deny), SOFT_WARN (allow + warning) |
| `afterFileEdit` | `.cursor/hooks/scripts/post-edit.py` | Diagnostic `ruff check` / `tsc` on edited files; does not modify sources |
| `stop` | `.cursor/hooks/scripts/stop.py` | Session outcome classification (4-gate), outbox + sidecar socket when Option C is enabled |

Thin wrappers `on_prompt.py`, `on_shell.py`, `on_edit.py`, `on_stop.py` may still exist for alternate setups; **Cursor loads the `scripts/` paths above**. Supporting modules: `_common.py`, `pattern_loader.py`, `hooks/lib/*`. All hook commands use stdlib only.

## Python library (tests & CI)

| Concern | Module |
|---------|--------|
| Category → routing context | `omnicursor.agents.get_agent_context` |
| Load `skills/*.md` | `omnicursor.skills.SkillRepository` |
| Keyword compliance checks | `omnicursor.compliance.check_compliance` |

## Agent Configs

17 JSON configs in [`.cursor/agents/`](./.cursor/agents/) define activation patterns for prompt-based routing. Hooks (`.cursor/hooks/scripts/user-prompt-submit.py` → `agent_scoring.score_agent`) and `agents.py` share the same scoring engine (`HARD_FLOOR = 0.55`; see `src/omnicursor/scoring.py`).

## Skills

17 Markdown skills in [`skills/`](./skills/): methodology documents the model reads from disk (paths in each rule / QUICKSTART). Each begins with YAML frontmatter whose **`name`** is **`onex-<slug>`** (matching the filename stem), uses `# onex-<slug>` as the Markdown title for humans, carries a compliance registry entry in `src/omnicursor/compliance.py`, and has a mirrored copy at `.cursor/skills/onex-<slug>/SKILL.md`. The Cursor **`/`** picker normally labels each skill from that **subdirectory** name (`onex-<slug>`), so it matches canonical ids—not the bare slug alone.

## Directory guides

Major folders include **`README.md`** (e.g. `.cursor/`, `docs/`, `skills/`, `src/omnicursor/`, `tests/`).

## Repository Layout

```text
OmniCursor/
├── .cursor-plugin/
│   └── plugin.json         # Official Cursor plugin manifest
├── .cursor/
│   ├── rules/              # Cursor rules (.mdc)
│   ├── hooks/              # Hook scripts + helpers
│   ├── hooks.json
│   ├── skills/             # Agent skills (onex-*/SKILL.md)
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

- [`CLAUDE.md`](./CLAUDE.md) — Commands, architecture, conventions
- [`docs/INDEX.md`](./docs/INDEX.md) — Map of all active docs
- [`docs/QUICKSTART.md`](./docs/QUICKSTART.md) — Setup, hooks, skills
- [`docs/CURRENT_STATE.md`](./docs/CURRENT_STATE.md) — What works today (Options A/B/C)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — Starter-pack buckets / adapter contract
- [`docs/archive/`](./docs/archive/README.md) — Completed plans, handoffs, capstone artifacts

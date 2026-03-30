# OmniCursor

Cursor-native MCP integration layer for OmniNode — combining rules, hooks, and tools into a deterministic AI workflow.

## Architecture

OmniCursor has three complementary layers:

1. **Cursor Rules** (7 `.mdc` files) — behavior surface for routing and interaction; always-on + activatable
2. **Cursor Hooks** (4 lifecycle scripts) — deterministic Python scripts, no LLM, fire on editor events
3. **MCP Tools** (3 tools) — structured backend for agent routing, skill invocation, and compliance validation

## Current Status

- **Phase 1**: Cursor rules ported from omniclaude
- **Phase 2**: MCP server with 3 tools + 5 skills
- **Phase 3A**: Hooks infrastructure + 16 agent configs
- **Phase 3B**: `beforeMCPExecution` + `beforeReadFile` (planned)

Not yet implemented: Kafka pipeline, Qdrant, full Linear integration, ONEX runtime parity.

## Quick Start

```bash
python3.10 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
omnicursor-server
```

See [`docs/QUICKSTART.md`](./docs/QUICKSTART.md) for full setup instructions.

## Hooks

Deterministic Python scripts that run on Cursor lifecycle events. Configured in `.cursor/hooks.json`.

| Hook | Script | What it does |
|------|--------|--------------|
| `beforeSubmitPrompt` | `on_prompt.py` | Classifies prompt intent against 16 agents, logs events |
| `beforeShellExecution` | `on_shell.py` | Guards against dangerous commands (deny/warn/allow) |
| `afterFileEdit` | `on_edit.py` | Logs edits, runs diagnostic `ruff check` on Python files |
| `stop` | `on_stop.py` | Aggregates session metrics to `~/.omnicursor/sessions/` |

All hooks use stdlib only (no pip dependencies). Shared utilities live in `_common.py`.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `get_agent_context(category)` | Returns routing context for a rule-selected category |
| `invoke_skill(skill_name)` | Loads a Markdown skill from the `skills/` directory |
| `check_compliance(skill_name, response_summary)` | Validates model output against a skill's expected pattern |

## Agent Configs

16 JSON configs in [`.cursor/agents/`](./.cursor/agents/) define activation patterns for prompt-based agent routing. Each config specifies `explicit_triggers` (2 pts) and `context_triggers` (1 pt) used by both hooks (`on_prompt.py`) and MCP (`get_agent_context`).

## Skills

| Skill | Purpose |
|-------|---------|
| `systematic-debugging` | Reproduce, hypothesize, verify, fix |
| `brainstorming` | Refine ideas into design docs through collaborative dialogue |
| `writing-plans` | Convert designs into TDD implementation plans |
| `plan-ticket` | Generate YAML ticket contract templates with repo detection |
| `adapter-stub` | Bucket 3 dry-run stubs with fail-soft behavior |

## Repository Layout

```text
OmniCursor/
├── .cursor/
│   ├── rules/              # 7 Cursor rules (.mdc)
│   ├── hooks/              # 4 lifecycle hook scripts + _common.py
│   ├── hooks.json           # Hook configuration
│   └── agents/             # 16 JSON agent configs
├── docs/                   # Architecture, quickstart, guides
├── skills/                 # 5 Markdown skill files
├── src/omnicursor/         # Python MCP backend
├── tests/                  # Unit tests (122 tests)
├── pyproject.toml          # Package config
└── OMNICLAUDE_SKILLS.md    # Read-only skill reference
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Documentation

- [`docs/QUICKSTART.md`](./docs/QUICKSTART.md) — Setup, MCP tools, hooks, and end-to-end flow
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — Bucket model and frozen adapter contract
- [`docs/DEVELOPER.md`](./docs/DEVELOPER.md) — Mapping from starter kit to backend
- [`docs/STUDENT_GUIDE.md`](./docs/STUDENT_GUIDE.md) — Capstone project roadmap
- [`HOW_TO_RUN_IN_CURSOR.md`](./HOW_TO_RUN_IN_CURSOR.md) — Original starter-pack guide

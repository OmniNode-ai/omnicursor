# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3.10 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run MCP server
omnicursor-server

# Tests
pytest tests/ -v              # full suite (122 tests)
pytest tests/test_agents.py -v  # single file
pytest tests/ -k "test_debug"   # by name pattern

# Lint (diagnostic only)
ruff check src/ tests/
```

## Architecture

OmniCursor is a Cursor-native MCP integration layer for OmniNode with three layers:

1. **Cursor Rules** (`.cursor/rules/`, 7 `.mdc` files) — behavior surface. Rules `00`/`01` are always-on; `10`-`20` activate on keyword match. Rules call MCP tools for routing, skills, and compliance.
2. **Cursor Hooks** (`.cursor/hooks/`, 4 Python scripts) — deterministic lifecycle scripts, stdlib only, no LLM. Configured in `.cursor/hooks.json`.
3. **MCP Tools** (`src/omnicursor/server.py`, 3 tools) — FastMCP backend for `get_agent_context`, `invoke_skill`, `check_compliance`.

### Agent routing has two merge layers

`agents.py` merges hardcoded `AGENT_CONTEXTS` (5 categories: debugging, brainstorming, planning, ticketing, adapter) with dynamically loaded JSON from `.cursor/agents/*.json` (16 configs). JSON overlays hardcoded via `{**AGENT_CONTEXTS, **_JSON_AGENTS}`. The `ALIASES` dict maps shorthand names to canonical categories.

### Trigger scoring (used by hooks and `match_agent()`)

Each agent config has `explicit_triggers` (2 pts each) and `context_triggers` (1 pt each). Score = points earned / max possible points. Case-insensitive substring matching. Highest score wins; no match returns `DEFAULT_CONTEXT`.

### Hook execution model

- Only `on_shell.py` (`beforeShellExecution`) can block execution via `{"permission": "deny"}`.
- All other hooks (`on_prompt.py`, `on_edit.py`, `on_stop.py`) are informational — Cursor ignores their stdout. They log to `~/.omnicursor/events.jsonl`.
- All hooks communicate via stdin/stdout JSON and use stdlib only.

### 3-bucket classification (from Cursor rules)

- **Bucket 1** (brainstorming, writing-plans): pure methodology, no external calls.
- **Bucket 2** (plan-ticket): reads bounded local files only.
- **Bucket 3** (adapter-stub): external integration, always `dry_run: true` first, fail-soft on error.

## Key constraints

- `omniclaude-main/` is a **read-only reference** — never modify it.
- `.cursor/rules/*.mdc` are teaching artifacts — modify with care.
- Hooks must use **Python stdlib only** (no pip dependencies).
- `on_edit.py` runs `ruff check` diagnostically — never `--fix`, never modifies files.
- `schemas.py` defines `AgentContext`, `SkillDocument`, `ComplianceResult` (Pydantic v2). The MCP server and agents module both depend on these models.
- Compliance checking (`compliance.py`) uses a hardcoded `COMPLIANCE_REGISTRY` with keyword-based pattern matching per skill.
- When adding a new agent: create `.cursor/agents/<name>.json` with `name`, `description`, `category`, `activation_patterns`, `instructions`, `recommended_skill`. It auto-loads on startup.
- When adding a new skill: create `skills/<name>.md`. Add a compliance registry entry in `compliance.py` if validation is needed.

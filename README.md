# OmniCursor

Cursor-native adaptation of OmniClaude — **rules**, **hooks**, **skills**, and **agent routing** for every workspace you open in Cursor. A Python library under `src/omnicursor/` backs pytest and CI; hooks stay stdlib-only at runtime.

## What it does

- **Routes prompts** to the best-matching agent (17 configs, shared scoring engine)
- **Guards shell commands** — hard-blocks dangerous patterns, warns on risky ones
- **Runs diagnostic lint** on Python/TypeScript edits (never auto-fixes)
- **Classifies session outcomes** and writes recaps for the next chat
- **Teaches methodology** via 17 file-backed skills (brainstorm → plan → ticket → PR review → handoff)

Works **offline by default**. Optional OmniNode stack integration (pattern sync, Kafka events, OmniMarket nodes) is documented in [ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Quick start

Install once as a [Cursor plugin](https://cursor.com/docs/plugins):

```bash
git clone https://github.com/OmniNode-ai/OmniCursor ~/tools/OmniCursor
cd ~/tools/OmniCursor
./scripts/install-plugin.sh
```

Restart Cursor (**Developer: Reload Window**). Confirm rules and skills appear under **Settings → Rules**.

Full guide: **[docs/QUICKSTART.md](./docs/QUICKSTART.md)**

## Architecture (four layers)

```
Rules + Skills + Agents     ← behavior surface (.cursor/rules, skills/, .cursor/agents)
        ↓
Hooks (4 lifecycle scripts) ← deterministic, stdlib-only (.cursor/hooks/scripts/)
        ↓
~/.omnicursor/              ← local patterns, events, sessions, outbox
        ↓
src/omnicursor/             ← tests, sidecar, drainer, OmniMarket bridge (optional)
```

Deep dive: **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**

## Hooks

Configured in [`.cursor/hooks.json`](./.cursor/hooks.json).

| Hook | Script | What it does |
|------|--------|--------------|
| `beforeSubmitPrompt` | `user-prompt-submit.py` | Agent scoring, learned-pattern injection, delegation rule |
| `beforeShellExecution` | `shell-guard.py` | Two-tier command guard (HARD_BLOCK / SOFT_WARN) |
| `afterFileEdit` | `post-edit.py` | Diagnostic `ruff check` / `tsc` — does not modify files |
| `stop` | `stop.py` | Session outcome (4-gate), recap, durable outbox write |

Supporting code: `.cursor/hooks/lib/`, `_common.py`, `pattern_loader.py`. All hook commands use **stdlib only**.

## Skills (17)

Canonical Markdown in [`skills/`](./skills/), mirrored for Cursor at [`.cursor/skills/onex-<slug>/SKILL.md`](./.cursor/skills/). Each skill id is **`onex-<slug>`** (YAML `name`, `/` picker, compliance registry).

| Bucket | Skills |
|--------|--------|
| **1 — Methodology** | brainstorming, writing-plans, systematic-debugging, pr-review, pr-polish, hostile-reviewer, defense-in-depth, docs-reality-sync, merge-planner, insights-to-plan, plan-review, handoff, recap, using-git-worktrees |
| **2 — Local files** | plan-ticket |
| **3 — External services** | plan-to-tickets, execute-plan (Linear MCP + OmniMarket) |

## Python library

| Module | Role |
|--------|------|
| `scoring.py` / `agents.py` | Agent routing (shared with hooks) |
| `skills.py` | Load skill Markdown |
| `compliance.py` | Keyword rubric checks |
| `session_outbox.py` | Durable outbox for Option C |
| `sidecar/` + `drainer/` | Outbox → Kafka/OmniDash publisher |
| `omnimarket_bridge.py` | Subprocess bridge to local OmniMarket nodes |

Details: [`src/omnicursor/README.md`](./src/omnicursor/README.md)

## Repository layout

```text
OmniCursor/
├── .cursor-plugin/plugin.json   # Cursor plugin manifest
├── .cursor/
│   ├── rules/                   # 14 .mdc rules (4 always-on)
│   ├── hooks/                   # Hook scripts + lib/
│   ├── hooks.json
│   ├── skills/                  # onex-*/SKILL.md mirrors
│   └── agents/                  # 17 JSON routing configs
├── docs/                        # QUICKSTART, ARCHITECTURE
├── skills/                      # Canonical skill Markdown
├── src/omnicursor/              # Python library + node contracts
├── tests/
├── scripts/install-plugin.sh
└── pyproject.toml
```

## Developer setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
pytest tests/ -v
ruff check src/ tests/ .cursor/hooks/
```

The tracked pre-commit hook runs the same checks as CI (`ruff`, `pytest`, skill compliance). Use `git commit --no-verify` only for emergency bypasses.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/QUICKSTART.md](./docs/QUICKSTART.md) | Install, hooks, skills, Linear MCP, privacy |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Layers, buckets, routing, intelligence A/B/C |
| [docs/README.md](./docs/README.md) | Documentation map |

Directory guides: `.cursor/`, `docs/`, `skills/`, `src/omnicursor/`, `tests/` each have a `README.md`.

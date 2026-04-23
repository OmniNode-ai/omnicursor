# OmniCursor Developer Notes

## Preserved Starter-Kit Inputs

These existing files were reviewed and intentionally preserved as the architectural base:

- [`.cursor/rules/00-omninode-concepts.mdc`](../.cursor/rules/00-omninode-concepts.mdc): always-on vocabulary, pipeline stages, bucket boundaries
- [`.cursor/rules/01-codebase-research.mdc`](../.cursor/rules/01-codebase-research.mdc): bounded file-research guard
- [`.cursor/rules/10-brainstorming.mdc`](../.cursor/rules/10-brainstorming.mdc): idea-to-design methodology
- [`.cursor/rules/13-systematic-debugging.mdc`](../.cursor/rules/13-systematic-debugging.mdc): structured debugging methodology
- [`.cursor/rules/11-writing-plans.mdc`](../.cursor/rules/11-writing-plans.mdc): design-to-plan methodology
- [`.cursor/rules/12-plan-ticket.mdc`](../.cursor/rules/12-plan-ticket.mdc): bounded repo detection and YAML ticket template generation
- [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md): frozen adapter contract and bucket rules (starter-pack artifact; Bucket 3 operational rules are not shipped in this repo)
- [`STUDENT_GUIDE.md`](./STUDENT_GUIDE.md): capstone execution and grading flow (starter-pack artifact)
- [`SKILL_TRANSLATION_TEMPLATE.md`](./SKILL_TRANSLATION_TEMPLATE.md): rule-porting template (starter-pack artifact)
- [`tests/prompts`](../tests/prompts): prompt fixtures for rule behavior
- [`tests/rubrics`](../tests/rubrics): pass/fail criteria for the preserved rules
- [`HOW_TO_RUN_IN_CURSOR.md`](./HOW_TO_RUN_IN_CURSOR.md): original starter-pack setup instructions (historical — see note below)
- [`OMNICLAUDE_SKILLS.md`](../OMNICLAUDE_SKILLS.md): omniclaude skill **reference** (optional when adding a new curated skill)

**OmniCursor extensions (not starter-pack originals):**

- [`.cursor/rules/14-pr-review.mdc`](../.cursor/rules/14-pr-review.mdc): PR / merge-readiness (`review` → `.cursor/skills/pr-review/SKILL.md`)
- [`.cursor/rules/15-handoff.mdc`](../.cursor/rules/15-handoff.mdc): session handoff (`handoff` → `.cursor/skills/handoff/SKILL.md`)

## Architecture (rules + hooks + library)

OmniCursor extends the starter kit with **hooks** and a **Python library**:

### Layer 1: Cursor Rules (preserved)

The preserved rules stay as the top-level behavior layer inside Cursor. Rules `00`/`01` are always-on; `10`–`15` activate on keyword match (including extensions `14`–`15`).

### Layer 2: Cursor Hooks (`.cursor/hooks/`)

4 hook entrypoints registered in `.cursor/hooks.json`, plus 2 supporting modules. Deterministic Python scripts, stdlib only — no pip dependencies.

| Script | Event | Purpose |
|--------|-------|---------|
| `on_prompt.py` | `beforeSubmitPrompt` | Three-strategy agent scoring, pattern injection, emits `{"systemMessage": ...}` (whether Cursor consumes this is a platform uncertainty) |
| `on_shell.py` | `beforeShellExecution` | Two-tier command guard (9 HARD_BLOCK + 11 SOFT_WARN patterns) |
| `on_edit.py` | `afterFileEdit` | Diagnostic `ruff check` on `.py` files, event logging |
| `on_stop.py` | `stop` | Session event aggregation, 4-gate outcome classification |
| `_common.py` | (shared) | Path constants, stdin/stdout helpers, event logging, agent config loading |
| `pattern_loader.py` | (library) | Thread-safe in-memory pattern cache, loads from `~/.omnicursor/learned_patterns.json` |

### Layer 3: Python library (`src/omnicursor/`)

Structured helpers for **tests**, **CI**, and optional scripting.

| Module | Purpose |
|--------|---------|
| `agents.py` | Agent routing with three-strategy scoring (exact/fuzzy/keyword), `HARD_FLOOR = 0.55`, dynamic JSON loading from `.cursor/agents/*.json`, `get_agent_context(category)` |
| `skills.py` | Auto-discovers and loads Markdown skills from `.cursor/skills/<name>/SKILL.md` |
| `compliance.py` | Keyword-based compliance registry with 3–5 checks per skill |
| `node_contracts.py` | Cursor-native node `contract.yaml` validation |
| `schemas.py` | Pydantic v2 models: `AgentContext`, `SkillDocument`, `ComplianceResult`, `PatternRecord`, `DatabaseStatus` |
| `patterns.py` | Lists 4 preserved rules as `PatternRecord` objects (static) |
| `db.py` | Repo paths (`REPO_ROOT`, `SKILLS_DIR`, `RULES_DIR`) and `InMemoryDatabase` placeholder |

## How Agent Routing Works

Routing logic lives in **one canonical module**: `.cursor/hooks/lib/agent_scoring.py` (stdlib only). Both `on_prompt.py` (hooks) and `agents.py` (library, via importlib bridge) delegate to it — no duplication. See [`ROUTING_DEDUPLICATION.md`](./ROUTING_DEDUPLICATION.md) for the importlib bridge pattern. Learned-pattern filtering shares a separate stdlib module: `.cursor/hooks/lib/prompt_pattern_selection.py`.

The three strategies are:

1. **Exact substring match** on `explicit_triggers` → 0.95, `context_triggers` → 0.80
2. **Fuzzy match** via `SequenceMatcher` with length-aware thresholds
3. **Keyword overlap** on `activation_keywords` → scaled 0.55–0.85

`HARD_FLOOR = 0.55` discards weak candidates. No match falls back to `polymorphic-agent` (hooks) or `omnicursor-generalist` (library default context).

Agent definitions are loaded dynamically from `.cursor/agents/*.json` (17 configs). Each config has: `name`, `description`, `category`, `activation_patterns` (with `explicit_triggers`, `context_triggers`, `activation_keywords`), `instructions`, `recommended_skill`.

## How routing integrates with rules

Hooks attempt **automatic** classification via `beforeSubmitPrompt`. Rules instruct the model to **read** `.cursor/skills/<name>/SKILL.md` and to use hook `systemMessage` hints when present.

`get_agent_context(category)` in `agents.py` is the **test/CI** view of the same routing metadata — not a second routing system in the IDE. For example, `13-systematic-debugging.mdc` tells the model to read `.cursor/skills/systematic-debugging/SKILL.md` after self-classifying as debugging.

## Adding New Components

**New agent**: Create `.cursor/agents/<name>.json` with `name`, `description`, `category`, `activation_patterns` (must include `explicit_triggers`, `context_triggers`, `activation_keywords`), `instructions`, `recommended_skill`. It auto-loads on startup.

**New skill**: Create `.cursor/skills/<name>/SKILL.md` with YAML frontmatter (`name:`, `description:`). Add a compliance registry entry in `compliance.py` with 3–5 keyword checks. Update the expected sets in `tests/test_compliance.py` and `tests/test_skills.py`.

## Historical Starter-Pack Docs

These files are preserved as starter-pack / capstone artifacts. They describe the original assignment scope and may not fully reflect the current implementation:

- `docs/ARCHITECTURE.md` — bucket model and frozen adapter contract (still accurate for its scope)
- `STUDENT_GUIDE.md` — 6-phase capstone execution plan
- `SKILL_TRANSLATION_TEMPLATE.md` — rule-porting template
- `HOW_TO_RUN_IN_CURSOR.md` — original setup instructions (references `cursor-omninode/` folder name and pre-hooks state; see [`docs/QUICKSTART.md`](../QUICKSTART.md) for current setup)

# Phase 3A — Historical Summary

> **Note**: This is a historical snapshot from the start of Phase 3A planning. The implementation described in the plan below has been **fully completed**. For current state, see [`HANDOFF.md`](./HANDOFF.md) and [`cursor.md`](../../cursor.md).

---

## 1. State at the Start of Phase 3A

> **Historical:** Early OmniCursor had **Cursor rules** (7 `.mdc` files) and a Python package under `src/omnicursor/` used for structured helpers; today that package is the **library** for tests/CI while IDE behavior is rules + hooks + `skills/*.md`. Agent routing in `agents.py` began as a hardcoded dictionary of 5 categories with an alias table and a generalist fallback. There were no hooks, no dynamic agent loading, no session tracking.

## 2. What Was Learned from OmniClaude

- **hooks.json**: OmniClaude configures hooks per Claude Code lifecycle event with tool-name matchers routing to shell scripts.
- **agent_router.py (TriggerMatcher)**: Multi-strategy scoring — exact substring, fuzzy similarity, keyword overlap, word-boundary context checks.
- **agent_router.py (ConfidenceScorer)**: Weighted scoring across 4 dimensions: trigger (40%), context (30%), capability (20%), historical (10%).
- **bash_guard.py**: Two-tier command guard — HARD_BLOCK patterns deny; SOFT_ALERT patterns allow with notification.
- **stop.sh**: Session end hook — logs completion, emits Kafka events, displays summary banner.
- **Agent YAML configs**: Rich configs with identity, philosophy, capabilities, activation patterns, workflows, quality gates.

## 3. Key Differences: Cursor Hooks vs Claude Code Hooks

| Aspect | Cursor Hooks | Claude Code Hooks |
|--------|-------------|-------------------|
| **Event names** | `beforeSubmitPrompt`, `beforeShellExecution`, `beforeMCPExecution`, `beforeReadFile`, `afterFileEdit`, `stop` | `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SessionEnd`, `PreCompact` |
| **Control flow** | `beforeShellExecution` can control execution; `beforeSubmitPrompt`/`afterFileEdit` are informational only | `PreToolUse` can block; `UserPromptSubmit` can inject context |
| **Shell guard** | `beforeShellExecution` CAN block via `{"blocked": true, "reason": "..."}` stdout JSON | `PreToolUse` with Bash matcher blocks via exit code 2 |

## 4. What Was Implemented (all complete)

1. Created `.cursor/hooks.json` with 4 lifecycle hooks
2. Created `on_prompt.py` — classifier + enrichment-ready routing (now three-strategy scoring with `systemMessage` output)
3. Created `on_shell.py` — two-tier bash guard (now 9 HARD_BLOCK + 11 SOFT_WARN patterns)
4. Created `on_edit.py` — diagnostic `ruff check` on Python edits
5. Created `on_stop.py` — session aggregator (now with 4-gate outcome classification)
6. Created 16 agent JSON configs in `.cursor/agents/`
7. Updated `agents.py` with three-strategy scoring and dynamic JSON loading
8. Created `pattern_loader.py` for learned pattern cache
9. Tests written for all hooks and updated agent routing

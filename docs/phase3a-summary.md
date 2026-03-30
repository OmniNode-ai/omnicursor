# Phase 3A — Step 1: Read & Plan Summary

## 1. Current OmniCursor State

OmniCursor is a Cursor-native MCP integration layer with two layers: **Cursor rules** (7 `.mdc` files) as the behavior/routing surface, and a **Python MCP server** (`src/omnicursor/`) as the structured backend. The MCP server exposes 3 tools: `get_agent_context`, `invoke_skill`, and `check_compliance`. Agent routing in `agents.py` is a hardcoded dictionary of 5 categories (debugging, brainstorming, planning, ticketing, adapter) with an alias table and a generalist fallback. Each category maps to an `AgentContext` (name, description, instructions, recommended skill). Compliance checking in `compliance.py` is keyword-based: each skill has a list of checks, each check has a list of keywords, and a check passes if any keyword appears in the response summary. Skills are loaded as raw Markdown from `skills/`. There are no hooks, no dynamic agent loading, no session tracking.

## 2. What I Learned from omniclaude

- **hooks.json**: omniclaude configures hooks per Claude Code lifecycle event (SessionStart, SessionEnd, Stop, UserPromptSubmit, PreCompact, PreToolUse, PostToolUse) with tool-name matchers (regex) routing to shell scripts. PreToolUse alone has 13 hook entries.
- **agent_router.py (TriggerMatcher)**: Matches user prompts against agent triggers using an inverted index with exact substring matching, fuzzy similarity (SequenceMatcher), keyword overlap scoring, and word-boundary context checks. Produces scored matches sorted by confidence.
- **agent_router.py (ConfidenceScorer)**: Weighted scoring across 4 dimensions: trigger match (40%), context alignment (30%), capability relevance (20%), historical performance (10%).
- **bash_guard.py**: Two-tier command guard — `HARD_BLOCK` patterns (catastrophic/forbidden commands like `--no-verify`, `rm -rf /`, `mkfs`) exit code 2 to deny the tool call; `SOFT_ALERT` patterns (force push, `kill -9`, `curl|sh`) allow but fire a non-blocking Slack notification. Plus a `CONTEXT_ADVISORY` tier for informational warnings.
- **post-tool-use-ruff.sh**: Runs `ruff format` + `ruff check --fix` on the specific `.py` file just edited, with debouncing (2s), file size gating (<100KB), and tool availability caching. Runs in background subshell, non-blocking.
- **stop.sh**: Session end hook — logs completion, emits Kafka events (session outcome, utilization scoring), displays summary banner, clears correlation state, tracks performance timing.
- **debug-intelligence.yaml**: Rich agent config with identity, philosophy, capabilities (primary/secondary/specialized), activation_patterns (explicit + context triggers), workflows, quality gates, and collaboration points.
- **commit.yaml**: Agent config for semantic commit messages with activation triggers, domain context, intelligence integration (pre-commit quality gates, impact analysis), and semantic commit type taxonomy.
- **polymorphic-agent.yaml**: Coordinator agent with aliases, polymorphic transformation capability, dispatch enforcement directive, parallel execution best practices, and action logging integration specs.
- **research.yaml**: Research agent with systematic methodology phases, research categories, output templates, and collaboration points with other agents.

## 3. Key Differences: Cursor Hooks vs Claude Code Hooks

| Aspect | Cursor Hooks | Claude Code Hooks |
|--------|-------------|-------------------|
| **Event names** | `beforeSubmitPrompt`, `beforeShellExecution`, `beforeMCPExecution`, `beforeReadFile`, `afterFileEdit`, `stop` | `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SessionEnd`, `PreCompact` |
| **Control flow** | `beforeShellExecution`/`beforeMCPExecution`/`beforeReadFile` can control execution via stdout JSON; `beforeSubmitPrompt`/`afterFileEdit` are **informational only** (Cursor ignores stdout) | `PreToolUse` can block via exit code 2 + JSON; `UserPromptSubmit` can inject context via stdout; `PostToolUse` can inject feedback |
| **Config format** | `hooks.json` in plugin/workspace, same schema but different event names | `hooks.json` in `.claude/` or settings, uses matchers for tool names |
| **Implication for `on_prompt.py`** | `beforeSubmitPrompt` output is ignored by Cursor — cannot inject context. Can only classify + log. | `UserPromptSubmit` stdout IS injected into the conversation as system context |
| **Implication for `on_edit.py`** | `afterFileEdit` output is ignored — can run diagnostics (ruff) but cannot inject feedback into the conversation. Must rely on side-effects (file modification). | `PostToolUse` stdout IS injected, so ruff results can be surfaced to the model |
| **Shell guard** | `beforeShellExecution` CAN block via `{"blocked": true, "reason": "..."}` stdout JSON | `PreToolUse` with Bash matcher blocks via exit code 2 |

## 4. Implementation Plan (Steps 2–9)

1. **Create `hooks/hooks.json`** — Cursor hooks config with 4 hooks:
   - `beforeSubmitPrompt` → `on_prompt.py` (classifier + logger, informational only)
   - `beforeShellExecution` → `on_shell.py` (two-tier guard, can block)
   - `afterFileEdit` → `on_edit.py` (ruff diagnostics, informational only)
   - `stop` → `on_stop.py` (session aggregator)
   - Defer `beforeMCPExecution` and `beforeReadFile` to Phase 3B

2. **Create `hooks/on_prompt.py`** — Reads prompt from stdin JSON, classifies it against agent categories using keyword matching (simplified TriggerMatcher), logs classification to `~/.omnicursor/sessions/`. Does NOT attempt context injection (Cursor ignores `beforeSubmitPrompt` output). Outputs `{}`.

3. **Create `hooks/on_shell.py`** — Two-tier bash guard ported from omniclaude's `bash_guard.py`:
   - `HARD_BLOCK` patterns: `--no-verify`, `rm -rf /`, `mkfs`, `dd of=/dev/`, `shred`, obfuscated shell execution → stdout `{"blocked": true, "reason": "..."}`
   - `SOFT_ALERT` patterns: force push, `git reset --hard`, `kill -9`, `curl|sh` → log warning, output `{}` (allow)
   - Default: output `{}` (allow)
   - No Slack integration (OmniCursor is local-only for now)

4. **Create `hooks/on_edit.py`** — Runs `ruff check` (diagnostic only, no `--fix`) on the edited `.py` file. Logs results to `~/.omnicursor/sessions/`. Output is informational only (Cursor ignores `afterFileEdit` stdout). Includes debouncing and file size gating from omniclaude's approach.

5. **Create `hooks/on_stop.py`** — Session aggregator: reads stop event JSON, logs session summary (duration, tools used, completion status) to `~/.omnicursor/sessions/`. No Kafka, no Slack — local file logging only.

6. **Create 16 agent JSON configs in `agents/configs/`** — Port the omniclaude YAML agent definitions to simplified JSON format suitable for OmniCursor. Each config contains: `name`, `description`, `activation_patterns` (explicit_triggers + context_triggers), `capabilities`, `recommended_skill` (if applicable), `domain_context`. The 16 agents to port are the subset relevant to OmniCursor's scope (debugging, research, commit, brainstorming, planning, ticketing, adapter, polymorphic-agent, plus additional agents from the omniclaude configs directory).

7. **Update `src/omnicursor/agents.py`** — Replace the hardcoded `AGENT_CONTEXTS` dict with dynamic JSON loading from `agents/configs/`. Add a `match_agent(prompt: str)` function that implements simplified TriggerMatcher logic: exact trigger substring matching → keyword overlap scoring → fallback to generalist. Keep backward compatibility with `get_agent_context(category)`.

8. **Write tests** — Unit tests for all new hooks (`on_prompt`, `on_shell`, `on_edit`, `on_stop`), the updated `agents.py` with dynamic loading and `match_agent()`, and JSON config loading. Test the shell guard against known HARD_BLOCK and SOFT_ALERT patterns.

9. **Update README and docs** — Add hooks architecture section to README, update `docs/ARCHITECTURE.md` with hooks layer description, add setup instructions for enabling hooks in Cursor.

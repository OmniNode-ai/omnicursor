# Hooks in OmniCursor

## What Hooks Are

Hooks are lifecycle scripts that fire at defined points in an AI coding session. Both Claude Code (OmniClaude) and Cursor support hooks, but their surfaces are different. A hook receives a JSON payload via stdin, does work (classifies, guards, logs, enriches), and writes a JSON response to stdout. The hook process exits 0 — the response payload, not the exit code, controls behavior.

The key distinction: **some hooks are informational** (the IDE ignores stdout, the hook just logs) and **some are decisional** (the hook's response actively changes what happens next). In Cursor, only `beforeShellExecution` is decisional. Everything else is informational.

---

## How Events Work in OmniClaude

OmniClaude registers hooks in `plugins/onex/hooks/hooks.json`. It has 9 event types. Multiple scripts can fire per event, and `PreToolUse`/`PostToolUse` support regex tool matchers so a script only runs for specific tools.

| Event | Scripts | What Fires |
|---|---|---|
| `SessionStart` | `session-start.sh` | Starts the Kafka emit daemon (Unix socket background process), initializes session state in `~/.onex_state/`. Idempotent — may fire on reconnect. |
| `SessionEnd` | `session-end.sh` | Tears down session state, emits `session-ended` to Kafka. |
| `UserPromptSubmit` | `user-prompt-submit.sh`<br>`user-prompt-delegation-rule.sh`<br>`user_prompt_structured_handoff_nudge.sh` | Three scripts fire per prompt. Routing classifies the prompt and injects agent context. Delegation rule injects a hard behavioral constraint. Nudge fires once per session for complex unstructured prompts. Output: `{"hookSpecificOutput": {"additionalContext": "..."}}`. |
| `PreToolUse` | 13+ scripts with tool matchers | Fires before every tool call (`Edit`, `Write`, `Bash`, MCP tools, etc.). Scripts enforce authorization, pipeline gates, scope gates, convention injection, changeset guards, DoD completion checks, model routing. Can block by exiting non-zero. |
| `PostToolUse` | 13+ scripts with tool matchers | Fires after every tool call. Quality checks, ruff on edits, TSC on TS files, test reminders, auto-checkpoints, auto-hostile-review, delegation counting, git state verification, Kafka emission. |
| `Stop` | `stop.sh` | Session outcome classification, final Kafka emission. |
| `PreCompact` | `pre-compact.sh` | Fires before context window compaction. Emits a probe event. |
| `SubagentStart` | `subagent-start.sh` | Fires when a subagent is spawned. Records the delegation and sets up correlation context. |

OmniClaude's event output format is `{"hookSpecificOutput": {"additionalContext": "..."}}` — Claude Code accumulates `additionalContext` from all scripts that fire for the same event. Cursor's format is `{"systemMessage": "..."}` — these are different protocols and not interchangeable.

---

## What Cursor Exposes

Cursor supports exactly 4 hook events, registered in `.cursor/hooks.json`:

| Event | Analog |
|---|---|
| `beforeSubmitPrompt` | `UserPromptSubmit` |
| `beforeShellExecution` | `PreToolUse` (Bash matcher only) |
| `afterFileEdit` | `PostToolUse` (Edit/Write matchers) |
| `stop` | `Stop` |

`SessionStart`, `SessionEnd`, `PreCompact`, `SubagentStart`, and the full `PreToolUse`/`PostToolUse` surface (with per-tool matchers) have no Cursor equivalent. This is a platform constraint, not a gap that can be worked around in scripts.

---

## All 4 Events — What Was Ported and How Far

### Event 1 — `beforeSubmitPrompt` → `scripts/user-prompt-submit.py`

OmniClaude fires three separate scripts for `UserPromptSubmit`. Cursor fires one and uses only the last `systemMessage` if multiple scripts fire, so all three concerns were merged into a single script.

**What was ported in full:**

- **Agent routing** — three-strategy scoring (exact substring → fuzzy SequenceMatcher → keyword overlap), `HARD_FLOOR = 0.55`, fallback to `polymorphic-agent`. 17 agent configs loaded from `.cursor/agents/*.json`.
- **Delegation rule** — fires on every prompt. When the prompt is estimated to be multi-step (≥80 chars + complex verb + connective, or ≥2 complex verbs), the rule is injected with imperative **MUST** language. Otherwise advisory framing. Mirrors `user-prompt-delegation-rule.sh`.
- **Handoff nudge** — fires exactly once per session when a complex (≥50 chars), unstructured prompt is detected. Suppressed for structured prompts (Task:/Scope: fields) and `/skill` invocations. Per-session `handoff_nudge_fired` flag prevents repeat. Mirrors `user_prompt_structured_handoff_nudge.sh`.
- **Agent persona depth** — injects the full agent config: `description`, `instructions` list, `recommended_skill`. The model receives enough context to behave like the selected agent.
- **Relevance-filtered pattern injection** — patterns scored by domain match (1.0/0.6/0.3 base) + keyword overlap boost (up to +0.4). Only patterns scoring ≥0.7 are injected, ranked by score, capped at 5. Irrelevant patterns excluded rather than injected as noise.

**What was added beyond OmniClaude:**

- **Fake SessionStart** — `_init_session()` runs on the first prompt of each conversation. Writes `~/.omnicursor/sessions/current.json` with `conversation_id` and `started_at`. Touches a `session_initialized` flag so subsequent calls are no-ops. This is OmniCursor's substitute for the `SessionStart` event (which Cursor doesn't have). Trigger: `session_initialized` flag file absent from `~/.omnicursor/sessions/<conv_id>/`.
- **Correlation ID threading** — `_generate_correlation_id()` produces a 12-char hex UUID per prompt. Written into `current.json` as `latest_correlation_id` on every prompt so Events 2–4 can read it and link their log entries back to the triggering prompt.
- **HTML comment header** — machine-readable metadata block at the top of every `systemMessage`: `agent=`, `confidence=`, `patterns=`, `domain=`, `delegation=`, `correlation=`. Parseable by tests without touching the visible Markdown body.
- **Typed event log** — every call writes `event`, `conversation_id`, `correlation_id`, `generation_id`, `matched_agent`, `score`, `reason`, `patterns_injected`, `delegation_required`, `prompt_snippet` (≤100 chars), `hook_duration_ms` to `events.jsonl`.
- **Per-turn state reset** — clears `write_count`, `read_count`, `delegated` flag at the start of each prompt.

**What couldn't be ported:** The three-script separation (routing / delegation / nudge are one merged script in OmniCursor). No Kafka emission — local JSONL only.

---

### Event 2 — `beforeShellExecution` → `scripts/shell-guard.py`

OmniClaude's closest analog is `pre_tool_use_bash_guard.sh` under `PreToolUse`. In Cursor, `beforeShellExecution` is the only hook that can actually block execution.

**What was ported:**

- **Two-tier guard** — HARD_BLOCK (9 patterns, `"permission": "deny"`) and SOFT_WARN (11 patterns, `"permission": "allow"` + `agentMessage`). HARD_BLOCK always takes priority.
- **Pattern coverage** — HARD_BLOCK: `rm -rf /`, `rm -rf ~/`, `rm -rf /*`, `mkfs`, `dd if=...of=/dev/`, fork bomb, `--no-verify`, `>/dev/sda`, `base64 --decode | sh`. SOFT_WARN: `git push --force`, `git push -f`, `git reset --hard`, `DROP TABLE/DATABASE`, `TRUNCATE`, `curl/wget | sh`, `kill -9`, `chmod 777`, `sudo rm`, `eval`.
- **Sourcing note** — HARD_BLOCK patterns are hand-picked for OmniCursor, inspired by omniclaude's `bash_guard.py` but not a direct import. SOFT_WARN is entirely OmniCursor-native — the advisory allow+warn tier has no equivalent in omniclaude, which only hard-blocks.
- **Correlation threading** — reads `latest_correlation_id` from `current.json` (written by Event 1).
- **Typed event log** — `event`, `conversation_id`, `correlation_id`, `command` (≤500 chars), `decision` (allow/deny/warn), `reason`, `hook_duration_ms`.

**What couldn't be ported:** OmniClaude's bash guard is one of 13+ `PreToolUse` scripts. The other 12 (authorization shims, pipeline gates, scope gates, convention injectors, changeset guards, DoD guards, model router) have no Cursor equivalent — Cursor's `beforeShellExecution` only fires for shell commands, not file edits or MCP tool calls.

---

### Event 3 — `afterFileEdit` → `scripts/post-edit.py`

OmniClaude's closest analog is the ruff/TSC quality-check scripts under `PostToolUse`. Cursor fires `afterFileEdit` after every file save. This hook is informational only — stdout is always `{}`.

**What was ported:**

- **Language detection** — 9 extension mappings: `.py` → python, `.ts`/`.tsx` → typescript, `.js`/`.jsx` → javascript, `.yaml`/`.yml` → yaml, `.json` → json, `.md` → markdown; all else → other. Case-insensitive.
- **Ruff diagnostics** — for Python files only, runs `ruff check <file_path>` (never `--fix`, never modifies any file). Counts finding lines, logs to `~/.omnicursor/lint.jsonl` when findings exist. Returns 0 silently on `FileNotFoundError` or timeout — graceful if ruff is not installed.
- **Correlation threading** — reads `latest_correlation_id` from `current.json`.
- **Typed event log** — `event`, `conversation_id`, `correlation_id`, `file_path` (≤500 chars), `edit_count`, `language`, `ruff_findings`, `hook_duration_ms`.

**What couldn't be ported:** OmniClaude's `PostToolUse` fires after any tool call — Write, Bash, MCP, etc. Cursor's `afterFileEdit` only fires for file edits. TSC diagnostics for TypeScript (a PostToolUse script in OmniClaude) are not yet implemented — the language detection wiring is in place but `tsc --noEmit` is not called.

---

### Event 4 — `stop` → `scripts/stop.py`

Fires when Cursor ends the session. This hook is informational only — stdout is always `{}`.

**What was ported:**

- **Session aggregation** — reads `~/.omnicursor/events.jsonl`, filters to the current `conversation_id`, and counts: `prompts_classified`, unique `files_edited`, `languages` (sorted, excluding `"other"`), `shell_commands.allowed/denied/warned`. Duplicate file paths are deduplicated.
- **Outcome classification** (`derive_session_outcome`) — pure 4-gate decision tree, no side effects:
  - **Gate 1 — FAILED**: status in `{failed, error, aborted}` OR error markers in corpus (`\w*Error:`, `\w*Exception:`, `Traceback`, `N FAILED`). `0 FAILED` from pytest summaries is excluded.
  - **Gate 2 — SUCCESS**: `work_done > 0` (file edits + prompt classifications) AND completion markers present (`completed`, `done`, `finished`, `success`).
  - **Gate 3 — ABANDONED**: no completion markers AND session duration < 60 seconds.
  - **Gate 4 — UNKNOWN**: catch-all.
- **Session summary persistence** — writes `~/.omnicursor/sessions/<conversation_id>.json` with the full aggregated summary. Skipped if `conversation_id` is empty.
- **Correlation threading** — reads `latest_correlation_id` from `current.json`.
- **Typed event log** — `event`, `conversation_id`, `correlation_id`, `session_status`, `session_outcome`, `session_outcome_reason`, `hook_duration_ms`, `summary` (nested object).

**What couldn't be ported:** OmniClaude's `stop.sh` emits a final Kafka event. No Kafka in OmniCursor. OmniClaude also receives a richer stop payload (tool-call log, token counts); Cursor sends only `{conversation_id, status}`.

---

## Implementation

### File Structure

```
.cursor/
  hooks.json                          ← all 4 events registered
  hooks/
    lib/
      _common.py                      ← shared paths, I/O, logging, session context
      pattern_loader.py               ← thread-safe learned-patterns cache
    scripts/
      user-prompt-submit.py           ← Event 1 (606 lines)
      shell-guard.py                  ← Event 2 (148 lines)
      post-edit.py                    ← Event 3 (162 lines)
      stop.py                         ← Event 4 (321 lines)
```

The legacy scripts (`on_prompt.py`, `on_shell.py`, `on_edit.py`, `on_stop.py`) remain in `.cursor/hooks/` but are no longer registered in `hooks.json`. All active traffic routes through `scripts/`.

### `hooks.json` (current state)

```json
{
  "version": 1,
  "hooks": {
    "beforeSubmitPrompt":  [{"command": "python3 .cursor/hooks/scripts/user-prompt-submit.py"}],
    "beforeShellExecution":[{"command": "python3 .cursor/hooks/scripts/shell-guard.py"}],
    "afterFileEdit":       [{"command": "python3 .cursor/hooks/scripts/post-edit.py"}],
    "stop":                [{"command": "python3 .cursor/hooks/scripts/stop.py"}]
  }
}
```

### Shared Library (`lib/_common.py`)

All scripts add `lib/` to `sys.path` at startup:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
```

Provides: path constants (`OMNICURSOR_DIR`, `EVENTS_LOG`, `SESSIONS_DIR`, `LEARNED_PATTERNS_FILE`, `AGENTS_DIR`), `read_stdin()`, `write_stdout()`, `write_context()`, `log_event()`, `read_session_context()`, `load_agent_configs()`. Stdlib only — no pip dependencies.

### Cross-Event Session Bridge

Event 1 writes `~/.omnicursor/sessions/current.json` on every prompt:
```json
{
  "conversation_id": "abc-123",
  "started_at": "2026-04-14T00:00:00+00:00",
  "latest_correlation_id": "a3f9c2d14e8b"
}
```
Events 2–4 read this via `read_session_context()` to thread `correlation_id` into their log entries.

Session state files under `~/.omnicursor/sessions/<conversation_id>/`:
```
session_initialized      — flag: first prompt has run (fake SessionStart)
handoff_nudge_fired      — flag: nudge has fired this session
write_count              — per-turn counter reset each prompt
read_count               — per-turn counter reset each prompt
delegated                — flag cleared each prompt
```

### Node Contracts

Each script has a corresponding YAML node contract in `src/omnicursor/nodes/*/contract.yaml` describing the hook event, script path, blocking status, and capabilities. Validated at test time by `tests/test_node_contracts.py`.

---

## Tests

All tests run with `pytest tests/ -v`. **378 passed, 0 skipped.**

| File | Tests | Classes | What it covers |
|---|---|---|---|
| `test_suite_event1_prompt.py` | 115 | 14 | Session identity, correlation ID, pattern relevance, complexity estimator, agent persona, HTML header, delegation, typed schema, session correlation update |
| `test_suite_event2_shell.py` | 36 | 5 | HARD_BLOCK (9 patterns), SOFT_WARN (8 patterns), safe commands, correlation threading, typed event schema |
| `test_suite_event3_edit.py` | 55 | 6 | Language detection (15 cases), ruff diagnostics (10), handle_edit core (10), correlation threading (5), typed schema (12), robustness (3) |
| `test_suite_event4_stop.py` | 48 | 6 | Outcome gates (17), session aggregation (11), summary persistence (3), correlation threading (4), typed schema (11), robustness (2) |
| Other test files | 124 | — | Agents, skills, compliance, node contracts, schemas |

All hook test files use `importlib.util.spec_from_file_location` to force-load each script directly from disk, avoiding `sys.modules` collisions between the old and new `_common.py` versions.

---

## What OmniClaude Does That OmniCursor Cannot

| OmniClaude capability | Why it can't be ported |
|---|---|
| `PreToolUse`/`PostToolUse` on any tool | Cursor only has `afterFileEdit` — Write/Bash/MCP calls are invisible to hooks |
| Multiple scripts per event with tool matchers | Cursor fires one script per event, no matcher system |
| `SessionStart` hook | No Cursor equivalent; faked via first-prompt detection in Event 1 |
| Rich `Stop` payload | Cursor sends only `{conversation_id, status}` — no tool-call log, no token counts |
| Kafka / external bus emission | Not feasible in stdlib-only hooks; OmniCursor uses append-only JSONL |
| Auto-checkpoint on edit | No generic `PostToolUse` means no `git checkpoint` after every Write call |
| TSC diagnostics on TypeScript | Language detection wiring is in place in `post-edit.py`; `tsc --noEmit` not yet called |

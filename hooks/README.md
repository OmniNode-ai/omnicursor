# Cursor lifecycle hooks

Deterministic **Python 3** scripts — **stdlib only**, no pip dependencies. They communicate via **stdin JSON / stdout JSON** as required by Cursor.

**Active entrypoints:** `hooks/hooks.json` invokes the scripts under `scripts/`:

| Script | Event (see `hooks.json`) | Role |
|--------|--------------------------|------|
| `scripts/session-start.py` | `sessionStart` | Session init + best-effort daemon-ensure + emit `session-started`; **injects** session-level context (baseline patterns + delegation rule + prior session) via `additional_context`. |
| `scripts/user-prompt-submit.py` | `beforeSubmitPrompt` | Agent scoring + emit for backend learning. **Block/observe-only** (`{continue, user_message}`); returns `{"continue": true}`. Does **not** inject — Cursor ignores `systemMessage` here. |
| `scripts/shell-guard.py` | `beforeShellExecution` | Shell guard — **only** hook that may **deny**. Returns `{permission: allow\|deny\|ask, user_message, agent_message}`. |
| `scripts/post-edit.py` | `afterFileEdit` | Log edits; diagnostic `ruff check` / `tsc` (never `--fix`); emit `tool-executed`. |
| `scripts/post-tool-use.py` | `postToolUse` | **Refreshes** injected patterns via `additional_context` for the tool's inferred domain; emit `tool-executed`. |
| `scripts/stop.py` | `stop` | Session outcome (4-gate), recap, durable outbox write. Loop-end signal. |
| `scripts/session-end.py` | `sessionEnd` | Emit `session-ended` (true conversation close). Fire-and-forget. |

**Injection channels:** Cursor injects context only via `sessionStart.additional_context` (initial) and `postToolUse.additional_context` (refresh). `beforeSubmitPrompt` is block-only and cannot inject.

**Shared (`lib/`):** `_common.py` (paths, logging, `~/.omnicursor/events.jsonl`, session JSON helpers, `write_additional_context`), `context_injection.py` (shared context assembly + pattern fetch; single source for the intelligence service URL), `agent_scoring.py`, `pattern_loader.py`, `prompt_pattern_selection.py`, `emit_client.py` (Unix socket, `OMNICURSOR_EMIT_SOCKET`), and `pattern_sync.py` (omniintelligence HTTP pull, invoked best-effort at `sessionStart`). DoD/dispatch-claim regexes live under repo `config/`.

**Constraints:** stdlib only in hook processes; always exit 0 (failures are logged, not propagated); only `shell-guard` may deny. See [docs/ARCHITECTURE.md §4](../docs/ARCHITECTURE.md#4-hooks). Tests live under `tests/test_suite_*.py`.

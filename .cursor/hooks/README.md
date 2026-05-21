# Cursor lifecycle hooks

Deterministic **Python 3** scripts — **stdlib only**, no pip dependencies. They communicate via **stdin JSON / stdout JSON** as required by Cursor.

| Script | Event (see `hooks.json`) | Role |
|--------|--------------------------|------|
| `on_prompt.py` | `beforeSubmitPrompt` | Classify prompt; log (stdout is informational only). |
| `on_shell.py` | `beforeShellExecution` | Shell guard — **only** hook that may **deny** execution. |
| `on_edit.py` | `afterFileEdit` | Log edits; diagnostic `ruff check` on Python (never `--fix`). |
| `on_stop.py` | `stop` | Session metrics under `~/.omnicursor/sessions/`. |

**Active entrypoints:** `.cursor/hooks.json` invokes `scripts/user-prompt-submit.py`, `scripts/shell-guard.py`, `scripts/post-edit.py`, and `scripts/stop.py` (see `lib/` for shared code).

**Shared:** `lib/_common.py` — paths, logging, `~/.omnicursor/events.jsonl`, session JSON helpers.

**Phase 1 extras:** `lib/emit_client.py` (Unix socket, `OMNICURSOR_EMIT_SOCKET`), `lib/pattern_sync.py` (optional omniintelligence HTTP pull — **stop** runs it only when `OMNICURSOR_PATTERN_SYNC_HTTP=1`; default off per sponsor), `config/dod_enforcement.json` (DoD + optional dispatch-claim regexes).

**Constraints:** Summarized in [CLAUDE.md](../../CLAUDE.md). Tests live under `tests/test_hooks_*.py` and `tests/test_suite_event*.py`.

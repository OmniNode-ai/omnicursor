"""sessionStart hook — session init, daemon-ensure, and context injection.

Fires when Cursor creates a new composer conversation. This is the real
replacement for the old "fake SessionStart" heuristic (first beforeSubmitPrompt),
and the real home for context injection (which Cursor's beforeSubmitPrompt cannot
do). Responsibilities:

  1. Initialize session state (~/.omnicursor/sessions/) so downstream hooks and
     stop-time aggregation have a coherent per-conversation record.
  2. Best-effort daemon-ensure: fast-ping the shared emit daemon and, when it
     is not up, kick off a detached spawn (``lib/daemon_ensure.py`` — never
     waited on, no-op without an omnimarket interpreter); then emit
     ``onex.evt.omnicursor.session-started.v1`` (non-blocking; no-op if absent).
  3. Inject session-level context via ``additional_context`` — baseline learned
     patterns, the standing delegation rule, a one-time handoff tip, and
     prior-session continuity.

Local-only: on a background/cloud agent, daemon-ensure and pattern sync are
skipped (§1a.4), but context injection is still attempted (harmless if ignored).

Node contract: ``node_cursor_pattern_injection_compute``. Stdlib only; always
exits 0; never blocks Cursor.
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path

_hooks = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_hooks / "lib"))
sys.path.insert(0, str(_hooks.parent.parent / "src"))

from _common import (  # noqa: E402
    LEARNED_PATTERNS_FILE,
    SESSIONS_DIR,
    ensure_dirs,
    log_event,
    merge_session_json,
    read_stdin,
    write_additional_context,
)
from context_injection import (  # noqa: E402
    build_session_context,
    fetch_patterns,
    load_prior_session_summary,
)
from daemon_ensure import ensure_daemon  # noqa: E402
from emit_client import send_event  # noqa: E402
from pattern_sync import sync_learned_patterns  # noqa: E402


def _init_session(conversation_id: str, started_at: str) -> None:
    """Write current.json + sessions/<id>.json so downstream hooks can find the session."""
    if not conversation_id:
        return
    try:
        ensure_dirs()
        (SESSIONS_DIR / "current.json").write_text(
            json.dumps({"conversation_id": conversation_id, "started_at": started_at})
        )
        merge_session_json(
            conversation_id,
            {
                "conversation_id": conversation_id,
                "started_at": started_at,
                "first_prompt_at": None,
                "last_prompt_at": None,
                "ci_passing": False,
            },
            sessions_root=SESSIONS_DIR,
        )
    except OSError:
        pass


def main() -> None:
    _start = time.monotonic()
    context_block = ""
    try:
        data = read_stdin()
        conversation_id = data.get("conversation_id", "")
        session_id = data.get("session_id", "")
        is_background_agent = bool(data.get("is_background_agent", False))
        composer_mode = data.get("composer_mode", "")

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _init_session(conversation_id, now)

        # Best-effort daemon-ensure + pattern sync — local sessions only (§1a.4).
        # ensure_daemon() fast-pings and, when the daemon is down, spawns it
        # detached (never waited on); True means it answered the ping.
        daemon_up = False
        if not is_background_agent:
            try:
                daemon_up = ensure_daemon()
            except Exception:
                daemon_up = False
            try:
                sync_learned_patterns(LEARNED_PATTERNS_FILE)
            except Exception:
                pass

        # Session-level injection (no prompt yet → baseline 'general' patterns).
        patterns = fetch_patterns("general")
        prior_summary = load_prior_session_summary(conversation_id)
        context_block = build_session_context(
            patterns=patterns, prior_summary=prior_summary
        )

        hook_ms = int((time.monotonic() - _start) * 1000)
        log_event(
            {
                "event": "session_started",
                "conversation_id": conversation_id,
                "session_id": session_id,
                "is_background_agent": is_background_agent,
                "composer_mode": composer_mode,
                "daemon_available": daemon_up,
                "patterns_injected": len(patterns),
                "hook_duration_ms": hook_ms,
            }
        )

        send_event(
            "onex.evt.omnicursor.session-started.v1",
            {
                "conversation_id": conversation_id,
                "session_id": session_id,
                "is_background_agent": is_background_agent,
                "composer_mode": composer_mode,
                "started_at": now,
            },
        )
    except Exception:
        pass

    # additional_context is Cursor's real sessionStart injection channel.
    write_additional_context(context_block)


if __name__ == "__main__":
    main()

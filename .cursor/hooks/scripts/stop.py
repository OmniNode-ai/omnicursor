"""stop hook — aggregate session events and write summary.

Node contract: ``node_cursor_session_outcome_orchestrator``
(``src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/contract.yaml``).

Informational only — Cursor ignores stdout. Always exits cleanly.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

_hooks = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_hooks / "lib"))
sys.path.insert(0, str(_hooks.parent.parent / "src"))

from _common import (  # noqa: E402
    EVENTS_LOG,
    LEARNED_PATTERNS_FILE,
    SESSIONS_DIR,
    ensure_dirs,
    log_event,
    read_session_context,
    read_session_json,
    read_stdin,
    write_stdout,
)
from emit_client import send_event  # noqa: E402
from omnicursor.session_outcome import derive_session_outcome, format_recap  # noqa: E402
from pattern_sync import sync_learned_patterns  # noqa: E402

_RECAP_PATH: Path = Path.home() / ".omnicursor" / "last-recap.md"

# ---------------------------------------------------------------------------
# Session aggregation (hook-specific: reads EVENTS_LOG, writes session files)
# ---------------------------------------------------------------------------


def _load_events(conversation_id: str) -> List[Dict[str, Any]]:
    """Read EVENTS_LOG and return entries matching conversation_id."""
    events: List[Dict[str, Any]] = []
    try:
        if not EVENTS_LOG.exists():
            return events
        with EVENTS_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("conversation_id") == conversation_id:
                        events.append(entry)
                except (json.JSONDecodeError, TypeError):
                    continue
    except OSError:
        pass
    return events


def aggregate_session(conversation_id: str, status: str) -> Dict[str, Any]:
    """Build a session summary from logged events."""
    events = _load_events(conversation_id)

    prompts_classified = 0
    edited_files: set = set()
    languages: set = set()
    shell_allowed = 0
    shell_denied = 0
    shell_warned = 0

    for evt in events:
        event_type = evt.get("event", "")
        if event_type == "prompt_classified":
            prompts_classified += 1
        elif event_type == "file_edited":
            fp = evt.get("file_path", "")
            if fp:
                edited_files.add(fp)
            lang = evt.get("language", "")
            if lang and lang != "other":
                languages.add(lang)
        elif event_type == "shell_guard":
            decision = evt.get("decision", "allow")
            if decision == "deny":
                shell_denied += 1
            elif decision == "warn":
                shell_warned += 1
            else:
                shell_allowed += 1

    outcome, outcome_reason = derive_session_outcome(status, events)

    return {
        "conversation_id": conversation_id,
        "session_status": status,
        "session_outcome": outcome,
        "session_outcome_reason": outcome_reason,
        "prompts_classified": prompts_classified,
        "files_edited": len(edited_files),
        "shell_commands": {
            "allowed": shell_allowed,
            "denied": shell_denied,
            "warned": shell_warned,
        },
        "languages": sorted(languages),
    }


def _write_session_summary(conversation_id: str, summary: Dict[str, Any]) -> None:
    """Persist session summary, merging with existing session state."""
    try:
        ensure_dirs()
        path = SESSIONS_DIR / f"{conversation_id}.json"
        merged = {**read_session_json(conversation_id, sessions_root=SESSIONS_DIR), **summary}
        with path.open("w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _start = time.monotonic()
    try:
        data = read_stdin()
        conversation_id = data.get("conversation_id", "")
        status = data.get("status", "completed")

        session = read_session_context()
        correlation_id: str = session.get("latest_correlation_id", "")

        summary = aggregate_session(conversation_id, status)
        hook_ms = int((time.monotonic() - _start) * 1000)

        log_event({
            "event": "session_stopped",
            "conversation_id": conversation_id,
            "correlation_id": correlation_id,
            "session_status": status,
            "session_outcome": summary["session_outcome"],
            "session_outcome_reason": summary["session_outcome_reason"],
            "hook_duration_ms": hook_ms,
            "summary": summary,
        })

        if conversation_id:
            _write_session_summary(conversation_id, summary)

        try:
            _RECAP_PATH.write_text(format_recap(summary), encoding="utf-8")
        except OSError:
            pass

        send_event(
            "onex.evt.omnicursor.session-ended.v1",
            {
                "conversation_id": conversation_id,
                "correlation_id": correlation_id,
                "session_status": status,
                "session_outcome": summary["session_outcome"],
                "session_outcome_reason": summary["session_outcome_reason"],
                "summary": summary,
            },
        )
        if os.environ.get("OMNICURSOR_PATTERN_SYNC_HTTP", "").lower() in (
            "1",
            "true",
            "yes",
        ):
            sync_learned_patterns(LEARNED_PATTERNS_FILE)
    except Exception:
        pass
    write_stdout({})


if __name__ == "__main__":
    main()

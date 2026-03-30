"""stop hook — aggregate session events and write summary.

Informational only — Cursor ignores stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _common
from _common import ensure_dirs, log_event, read_stdin, write_stdout


# ---------------------------------------------------------------------------
# Session aggregation
# ---------------------------------------------------------------------------


def _load_events(conversation_id: str) -> List[Dict[str, Any]]:
    """Read events.jsonl and return entries matching *conversation_id*."""
    events: List[Dict[str, Any]] = []
    try:
        if not _common.EVENTS_LOG.exists():
            return events
        with _common.EVENTS_LOG.open("r", encoding="utf-8") as f:
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
    edited_files: set[str] = set()
    languages: set[str] = set()
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

    return {
        "conversation_id": conversation_id,
        "session_status": status,
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
    """Persist session summary to ~/.omnicursor/sessions/<id>.json."""
    try:
        ensure_dirs()
        path = _common.SESSIONS_DIR / f"{conversation_id}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        data = read_stdin()
        conversation_id = data.get("conversation_id", "")
        status = data.get("status", "completed")

        summary = aggregate_session(conversation_id, status)

        log_event(
            {
                "event": "session_stopped",
                "conversation_id": conversation_id,
                "session_status": status,
                "summary": summary,
            }
        )

        if conversation_id:
            _write_session_summary(conversation_id, summary)
    except Exception:
        pass
    write_stdout({})


if __name__ == "__main__":
    main()

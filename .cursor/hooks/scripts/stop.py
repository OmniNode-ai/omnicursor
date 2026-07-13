"""stop hook — aggregate session events and write summary.

Node contract: ``node_cursor_session_outcome_orchestrator``
(``src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/contract.yaml``).

Informational only — Cursor ignores stdout. Always exits cleanly.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from _common import (
    EVENTS_LOG,
    LEARNED_PATTERNS_FILE,
    SESSIONS_DIR,
    ensure_dirs,
    hook_enabled,
    log_event,
    read_session_context,
    read_session_json,
    read_stdin,
    write_stdout,
)
from emit_client import send_event
from omnicursor.pattern_writer import write_session_patterns
from omnicursor.session_outcome import derive_session_outcome, format_recap
from omnicursor.session_outbox import write_session_outcome

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


def _build_outbox_payload(
    summary: Dict[str, Any],
    events: List[Dict[str, Any]],
    conversation_id: str,
    correlation_id: str,
) -> Dict[str, Any]:
    """Aggregate prompt_classified events into the outbox payload schema v1."""
    matched_agent: Optional[str] = None
    matched_confidence: Optional[float] = None
    patterns_injected = 0
    seen_ids: Dict[str, None] = {}

    for evt in events:
        if evt.get("event") != "prompt_classified":
            continue
        matched_agent = evt.get("matched_agent", matched_agent)
        matched_confidence = evt.get(
            "matched_confidence",
            evt.get("score", matched_confidence),
        )
        patterns_injected += int(evt.get("patterns_injected", 0))
        for pid in evt.get("injected_pattern_ids", []):
            if pid:
                seen_ids[pid] = None

    started_at: Optional[str] = None
    for evt in events:
        ts = evt.get("ts") or evt.get("timestamp")
        if ts:
            started_at = str(ts)
            break

    return {
        "schema_version": "omnicursor.session_outcome.v1",
        "source": "omnicursor",
        "correlation_id": correlation_id,
        "conversation_id": conversation_id,
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session_status": summary.get("session_status", ""),
        "session_outcome": summary.get("session_outcome", ""),
        "session_outcome_reason": summary.get("session_outcome_reason", ""),
        "prompts_classified": int(summary.get("prompts_classified", 0)),
        "files_edited": int(summary.get("files_edited", 0)),
        "shell_commands": summary.get("shell_commands", {}),
        "languages": list(summary.get("languages", [])),
        "matched_agent": matched_agent,
        "matched_confidence": matched_confidence,
        "patterns_injected": patterns_injected,
        "injected_pattern_ids": list(seen_ids),
    }


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
        merged = {
            **read_session_json(conversation_id, sessions_root=SESSIONS_DIR),
            **summary,
        }
        with path.open("w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # A6 kill-switch/mask — short-circuit before ANY side effect (stdin read,
    # aggregation, summary/recap/outbox/learned_patterns writes, local log,
    # emits).
    if not hook_enabled("stop"):
        write_stdout({})
        return

    _start = time.monotonic()
    try:
        data = read_stdin()
        conversation_id = data.get("conversation_id", "")
        status = data.get("status", "completed")

        session = read_session_context()
        correlation_id: str = session.get("latest_correlation_id", "")

        summary = aggregate_session(conversation_id, status)
        hook_ms = int((time.monotonic() - _start) * 1000)

        events: List[Dict[str, Any]] = []
        outbox_payload: Optional[Dict[str, Any]] = None
        if conversation_id:
            events = _load_events(conversation_id)
            outbox_payload = _build_outbox_payload(
                summary, events, conversation_id, correlation_id
            )

        injected_for_log = (
            list(outbox_payload.get("injected_pattern_ids") or [])
            if outbox_payload is not None
            else []
        )

        log_event(
            {
                "event": "session_stopped",
                "conversation_id": conversation_id,
                "correlation_id": correlation_id,
                "session_status": status,
                "session_outcome": summary["session_outcome"],
                "session_outcome_reason": summary["session_outcome_reason"],
                "hook_duration_ms": hook_ms,
                "injected_pattern_ids": injected_for_log,
                "summary": summary,
            }
        )

        if conversation_id:
            _write_session_summary(conversation_id, summary)

        try:
            _RECAP_PATH.write_text(format_recap(summary), encoding="utf-8")
        except OSError:
            pass

        if conversation_id and outbox_payload is not None:
            write_session_patterns(
                LEARNED_PATTERNS_FILE,
                events,
                summary["files_edited"],
                summary["session_outcome"],
            )
            write_session_outcome(outbox_payload)

            _outcome = outbox_payload["session_outcome"]
            _error = (
                {
                    "code": "session_failed",
                    "message": outbox_payload["session_outcome_reason"],
                    "component": "omnicursor",
                }
                if _outcome == "failed"
                else None
            )
            try:
                send_event(
                    "session.outcome",
                    {
                        "session_id": conversation_id,
                        "outcome": _outcome,
                        "reason": outbox_payload["session_outcome_reason"],
                        "correlation_id": correlation_id,
                        "matched_agent": outbox_payload["matched_agent"],
                        "matched_confidence": outbox_payload["matched_confidence"],
                        "files_edited": outbox_payload["files_edited"],
                        "started_at": outbox_payload["started_at"],
                        "ended_at": outbox_payload["ended_at"],
                        "error": _error,
                    },
                )
            except Exception:
                pass

            _injected = outbox_payload.get("injected_pattern_ids") or []
            if _injected:
                try:
                    send_event(
                        "utilization.scoring.requested",
                        {
                            "session_id": conversation_id,
                            "correlation_id": correlation_id,
                            "session_outcome": _outcome,
                            "injected_pattern_ids": list(_injected),
                        },
                    )
                except Exception:
                    pass
    except Exception:
        pass
    write_stdout({})


if __name__ == "__main__":
    main()

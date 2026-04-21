"""stop hook — aggregate session events and write summary.

Node contract: ``node_cursor_session_outcome_orchestrator``
(``src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/contract.yaml``).

Port of on_stop.py to the scripts/ layer with:
  - Shared lib (lib/_common.py) via sys.path
  - Correlation threading: reads latest_correlation_id from current.json
  - Typed event schema: event, conversation_id, correlation_id, session_status,
    session_outcome, session_outcome_reason, hook_duration_ms, summary

Informational only — Cursor ignores stdout. Always exits cleanly.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from _common import (
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
from emit_client import send_event
from pattern_sync import sync_learned_patterns


# ---------------------------------------------------------------------------
# Outcome classification constants
# ---------------------------------------------------------------------------

# Sessions with no completion markers and duration below this threshold
# are classified as abandoned rather than unknown.
ABANDON_THRESHOLD_SECONDS: float = 60.0

# Error markers: exception/error class names at line start, Traceback, N FAILED
_ERROR_MARKER_REGEXES = (
    re.compile(r"(?:^|\n)\s*\w*Error:"),
    re.compile(r"(?:^|\n)\s*\w*Exception:"),
    re.compile(r"\bTraceback\b"),
    re.compile(r"[1-9]\d*\s+FAILED\b|[Tt]ests?\s+FAILED\b"),
)
_FAILED_EOL_RE = re.compile(r"\bFAILED\s*$", re.MULTILINE)
_ZERO_COUNT_PREFIX_RE = re.compile(r"\b0+\s+FAILED\b")

# Completion markers: word-boundary, case-insensitive
_COMPLETION_MARKER_REGEXES = tuple(
    re.compile(r"\b" + re.escape(m) + r"\b", re.IGNORECASE)
    for m in ("completed", "done", "finished", "success")
)


# ---------------------------------------------------------------------------
# Outcome signal helpers
# ---------------------------------------------------------------------------


def _has_error_markers(text: str) -> bool:
    """Return True if *text* contains any error markers.

    Standalone FAILED at end-of-line is checked with per-line zero-count
    exclusion to avoid matching '0 FAILED' from pytest summaries.
    """
    for pattern in _ERROR_MARKER_REGEXES:
        if pattern.search(text):
            return True
    for match in _FAILED_EOL_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line = text[line_start:match.end()]
        if not _ZERO_COUNT_PREFIX_RE.search(line):
            return True
    return False


def _has_completion_markers(text: str) -> bool:
    """Return True if *text* contains any completion markers (case-insensitive)."""
    for pattern in _COMPLETION_MARKER_REGEXES:
        if pattern.search(text):
            return True
    return False


def _events_to_text(events: List[Dict[str, Any]]) -> str:
    """Build a text corpus from session events for marker detection."""
    parts: List[str] = []
    for evt in events:
        event_type = evt.get("event", "")
        if event_type == "prompt_classified":
            parts.append(evt.get("reason", ""))
            parts.append(evt.get("prompt_snippet", ""))
        elif event_type == "file_edited":
            parts.append(evt.get("file_path", ""))
        elif event_type == "shell_guard":
            parts.append(evt.get("decision", ""))
    return "\n".join(p for p in parts if p)


def _compute_duration(events: List[Dict[str, Any]]) -> float:
    """Return elapsed seconds between first and last event timestamp.

    Returns 0.0 when fewer than two parseable timestamps are available.
    """
    timestamps: List[float] = []
    for evt in events:
        ts = evt.get("timestamp", "")
        if not ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            timestamps.append(dt.timestamp())
        except (ValueError, AttributeError):
            continue
    if len(timestamps) >= 2:
        return max(timestamps) - min(timestamps)
    return 0.0


def derive_session_outcome(
    status: str,
    events: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """Derive session outcome from Cursor status and the event log.

    4-gate decision tree (evaluated in order):

      Gate 1 — FAILED:
        status string maps to a failure code ("failed"/"error"/"aborted")
        OR error markers (\\w*Error:, \\w*Exception:, Traceback, N FAILED)
        are present in the event corpus.

      Gate 2 — SUCCESS:
        at least one unit of meaningful work was done (file edited or prompt
        classified) AND completion markers are present in the corpus.

      Gate 3 — ABANDONED:
        no completion markers AND session duration < ABANDON_THRESHOLD_SECONDS.

      Gate 4 — UNKNOWN:
        none of the above criteria met.

    Returns ``(outcome, reason)`` where outcome is one of:
    ``"failed"`` | ``"success"`` | ``"abandoned"`` | ``"unknown"``.

    Pure function — no side effects.
    """
    exit_failed = status.lower() in {"failed", "error", "aborted"}
    corpus = status + "\n" + _events_to_text(events)

    has_errors = _has_error_markers(corpus)
    has_completion = _has_completion_markers(corpus)
    duration = _compute_duration(events)

    work_done = sum(
        1 for e in events
        if e.get("event") in {"file_edited", "prompt_classified"}
    )

    # --- Gate 1: FAILED ---
    if exit_failed or has_errors:
        reason = (
            "Status indicates failure"
            if exit_failed
            else "Error markers detected in session events"
        )
        return ("failed", reason)

    # --- Gate 2: SUCCESS ---
    if work_done > 0 and has_completion:
        return (
            "success",
            "Session completed with {} work event{} and completion markers".format(
                work_done, "s" if work_done != 1 else "",
            ),
        )

    # --- Gate 3: ABANDONED ---
    if not has_completion and duration < ABANDON_THRESHOLD_SECONDS:
        return (
            "abandoned",
            "Session ended after {:.1f}s without completion markers".format(duration),
        )

    # --- Gate 4: UNKNOWN ---
    return ("unknown", "Insufficient signal to classify session outcome")


# ---------------------------------------------------------------------------
# Session aggregation
# ---------------------------------------------------------------------------


def _load_events(conversation_id: str) -> List[Dict[str, Any]]:
    """Read EVENTS_LOG and return entries matching *conversation_id*."""
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
    """Persist session summary, merging with existing session state (e.g. ci_passing)."""
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
        # Optional dev pull from omniintelligence HTTP — off by default (sponsor: capstone
        # pattern persistence is local / PG; see docs/dev/SPONSOR_ALIGNMENT_2026-04-16.md).
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

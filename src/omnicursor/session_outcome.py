# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Session outcome classification shared by node_cursor_session_outcome_orchestrator.

Extracted from .cursor/hooks/scripts/stop.py. Pure functions — no side effects,
no filesystem I/O. The hook script retains its own copy for stdlib-only execution.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Tuple

ABANDON_THRESHOLD_SECONDS: float = 60.0

_ERROR_MARKER_REGEXES = (
    re.compile(r"(?:^|\n)\s*\w*Error:"),
    re.compile(r"(?:^|\n)\s*\w*Exception:"),
    re.compile(r"\bTraceback\b"),
    re.compile(r"[1-9]\d*\s+FAILED\b|[Tt]ests?\s+FAILED\b"),
)
_FAILED_EOL_RE = re.compile(r"\bFAILED\s*$", re.MULTILINE)
_ZERO_COUNT_PREFIX_RE = re.compile(r"\b0+\s+FAILED\b")

_COMPLETION_MARKER_REGEXES = tuple(
    re.compile(r"\b" + re.escape(m) + r"\b", re.IGNORECASE)
    for m in ("completed", "done", "finished", "success")
)


def _has_error_markers(text: str) -> bool:
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
    for pattern in _COMPLETION_MARKER_REGEXES:
        if pattern.search(text):
            return True
    return False


def _events_to_text(events: List[Dict[str, Any]]) -> str:
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
      Gate 1 — FAILED: status maps to failure OR error markers in corpus.
      Gate 2 — SUCCESS: work done AND completion markers present.
      Gate 3 — ABANDONED: no completion markers AND duration < threshold.
      Gate 4 — UNKNOWN: none of the above.

    Returns (outcome, reason). Pure function — no side effects.
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

    if exit_failed or has_errors:
        reason = (
            "Status indicates failure"
            if exit_failed
            else "Error markers detected in session events"
        )
        return ("failed", reason)

    if work_done > 0 and has_completion:
        return (
            "success",
            "Session completed with {} work event{} and completion markers".format(
                work_done, "s" if work_done != 1 else "",
            ),
        )

    if not has_completion and duration < ABANDON_THRESHOLD_SECONDS:
        return (
            "abandoned",
            "Session ended after {:.1f}s without completion markers".format(duration),
        )

    return ("unknown", "Insufficient signal to classify session outcome")


def format_recap(summary: dict) -> str:
    """Generate a recap text block from an aggregate_session() result dict."""
    shell = summary.get("shell_commands", {})
    languages = summary.get("languages", [])
    lines = [
        "## Session Recap (auto)",
        f"**Outcome:** {summary.get('session_outcome', 'unknown')}",
        f"**Files edited:** {summary.get('files_edited', 0)}",
        f"**Prompts classified:** {summary.get('prompts_classified', 0)}",
        f"**Shell commands:** {shell.get('allowed', 0)} allowed, "
        f"{shell.get('warned', 0)} warned, {shell.get('denied', 0)} denied",
        f"**Languages:** {', '.join(languages) if languages else 'none'}",
    ]
    return "\n".join(lines)

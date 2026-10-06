"""Canonical ModelCursorHookEvent-shaped dict builder for hook emits (A3).

Hooks emit plain dicts under semantic registry keys (the ``stop.py`` pattern —
the registry YAML owns every topic string; a topic literal in a hook is a bug).
For keys that fan out to the restricted ``onex.cmd.omniintelligence.
cursor-hook-event.v1`` topic, the payload must deserialize into the backend's
``ModelCursorHookEvent`` (omnibase_core), which is ``extra="forbid"`` at the
top level: exactly the six canonical keys built here, with every non-canonical
field nested inside ``payload`` (``extra="allow"``).

Native Cursor hook names are normalized to the canonical event-type vocabulary
at emit time (mandated by ``enum_cursor_hook_event_type.py`` — Cursor shares
Claude Code's canonical hook lifecycle vocabulary).

Stdlib only; never import the pydantic model here — the backend validates.
"""

from __future__ import annotations

import datetime
import logging
import uuid

# Cursor native hook name -> canonical event_type
# (EnumClaudeCodeHookEventType values, reused by the Cursor alias enum).
_EVENT_NAME_MAP = {
    "beforeSubmitPrompt": "UserPromptSubmit",
    "stop": "Stop",
    "beforeShellExecution": "PreToolUse",
    "afterFileEdit": "PostToolUse",
    "postToolUse": "PostToolUse",
    "sessionStart": "SessionStart",
    "sessionEnd": "SessionEnd",
}


def normalize_event_name(native_hook: str) -> str:
    """Map a Cursor native hook name to its canonical event_type value."""
    return _EVENT_NAME_MAP.get(native_hook, native_hook)


def generate_correlation_id() -> str:
    """A full UUID string — the canonical ``correlation_id`` is ``UUID | None``.

    Never truncate (a 12-hex short id fails backend pydantic validation).
    """
    return str(uuid.uuid4())


def _valid_correlation_id(correlation_id: object) -> str | None:
    """Return *correlation_id* as a canonical UUID string, or None.

    Session state written by older hook versions may carry a 12-hex short id;
    anything that is not a full UUID is dropped to None rather than shipped to
    a validator that would reject the whole event.
    """
    if not correlation_id:
        return None
    try:
        return str(uuid.UUID(str(correlation_id)))
    except (ValueError, AttributeError, TypeError):
        return None


_LOG = logging.getLogger(__name__)
# Library convention: hook processes configure no logging, and without a
# handler the stdlib "lastResort" handler would print WARNINGs to the hook's
# stderr — a side channel no hook uses today. Records still propagate to any
# root handler (pytest's caplog, a future ~/.omnicursor log handler). The
# guard keeps the handler single when tests load this module more than once.
if not _LOG.handlers:
    _LOG.addHandler(logging.NullHandler())


def _valid_session_id(session_id: object) -> str:
    """Return *session_id* as a canonical UUID string, or ``""``.

    Mirror of ``_valid_correlation_id`` with ``""`` as the sink (never None:
    the wire field is a ``str`` and the registry's ``partition_key_field``).
    Backend ``agent_actions.session_id`` is a UUID column, so a non-UUID value
    would fail the INSERT and silently degrade the handler to PARTIAL. Real
    Cursor conversation ids are UUIDs; this guards synthesized/test events.
    """
    if not session_id:
        return ""
    try:
        return str(uuid.UUID(str(session_id)))
    except (ValueError, AttributeError, TypeError):
        _LOG.warning(
            'session_id %r is not a UUID; emitting session_id="" instead', session_id
        )
        return ""


def build_cursor_event(
    native_hook: str,
    session_id: str,
    payload: dict,
    correlation_id: str | None = None,
) -> dict:
    """Build the canonical ModelCursorHookEvent-shaped plain dict.

    Exactly the six top-level keys the backend model accepts; *payload* carries
    every event-specific field. The caller is responsible for redacting any
    prompt fragment inside *payload* (A5) before emitting.
    """
    return {
        "event_type": normalize_event_name(native_hook),
        "session_id": _valid_session_id(session_id),
        "correlation_id": _valid_correlation_id(correlation_id),
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "agent_source": "cursor",
        "payload": payload,
    }

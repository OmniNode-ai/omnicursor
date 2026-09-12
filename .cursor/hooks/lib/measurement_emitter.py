# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Measurement emission for Cursor sessions (stdlib only).

Gives a Cursor session the same measurement footprint a Claude session has.
Before this, Cursor emitted **zero** measurement events, so Cursor work was
invisible to promotion-gate and attribution analytics (OMNICURSOR plan, B5).

Wire shape
----------
Builds a ``ContractMeasurementEvent`` envelope wrapping ``ContractPhaseMetrics``
(``omnibase_spi.contracts.measurement``) as a plain dict and hands it to the
shared emit daemon via ``emit_client.send_event``. The hook stays stdlib-only
and never imports pydantic -- the SPI contracts are pydantic models, and hooks
run under a bare ``python3`` with no venv, so the envelope is constructed as
JSON here and validated downstream by the consumer.

Native fields, deliberately
---------------------------
``toolchain``, ``producer_kind`` and ``model_id`` are set as **native**
``ContractMeasurementContext`` fields, never inside ``extensions{}``.

OmniClaude's ``phase_instrumentation.py`` currently sets ``toolchain``
natively but buries ``model_id`` and ``producer_kind`` in ``extensions``
(:286-291), even though both are native on the contract (``model_id`` at
``contract_measurement_context.py:72``, ``producer_kind`` at ``:76``, where it
is a constrained ``Literal`` chosen specifically to prevent the free-string
drift ``extensions{}`` invites). That hybrid is legacy drift, not a standard to
copy: convergence runs the other way, and OmniClaude is expected to migrate
onto this shape. Do not mirror it here.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from emit_client import send_event

# Event type the registry fans out to onex.evt.omnicursor.phase-metrics.v1.
EVENT_TYPE = "phase.metrics"

# Discriminator inside the ContractMeasurementEvent envelope.
MEASUREMENT_EVENT_TYPE = "phase_completed"

PRODUCER_NAME = "omnicursor-hooks"

# ContractEnumPipelinePhase (enum_pipeline_phase.py).
VALID_PHASES = ("plan", "implement", "verify", "review", "release")

# ContractMeasurementContext.producer_kind is Literal["agent", "human", "unknown"].
VALID_PRODUCER_KINDS = ("agent", "human", "unknown")

_SCHEMA_VERSION = "1.0"


def _producer_version() -> str:
    """Best-effort plugin version; empty string is a valid contract default."""
    return os.environ.get("OMNICURSOR_VERSION", "")


def build_measurement_event(
    *,
    run_id: str,
    phase: str,
    wall_clock_ms: float,
    ticket_id: str = "",
    repo_id: str = "",
    model_id: str = "",
    producer_kind: str = "agent",
    phase_id: str = "",
    attempt: int = 1,
    instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a ContractMeasurementEvent-shaped dict for a completed phase.

    Args:
        run_id: Pipeline run identifier. Required by ContractPhaseMetrics.
        phase: One of VALID_PHASES. Anything else falls back to "implement",
            matching how OmniClaude handles an unknown phase rather than
            dropping the measurement.
        wall_clock_ms: Phase duration. Required by ContractDurationMetrics.
        ticket_id: Work-item identifier, when the session has one.
        repo_id: Repository identifier.
        model_id: Model that produced the work. NATIVE field.
        producer_kind: One of VALID_PRODUCER_KINDS. NATIVE field. Anything
            else falls back to "unknown", which is the contract default and
            the honest answer for an unrecognised value.
        phase_id: Unique id for this phase execution.
        attempt: 1-based attempt number for retried phases.
        instance_id: Producer instance id; generated when omitted.

    Returns:
        A JSON-serialisable dict matching the ContractMeasurementEvent wire
        format. Never raises -- callers are fire-and-forget hooks.
    """
    if phase not in VALID_PHASES:
        phase = "implement"
    if producer_kind not in VALID_PRODUCER_KINDS:
        producer_kind = "unknown"

    now = datetime.now(timezone.utc)

    context: Dict[str, Any] = {
        "ticket_id": ticket_id,
        "repo_id": repo_id,
        # NATIVE -- not extensions{}. See module docstring.
        "toolchain": "cursor",
        "model_id": model_id,
        "producer_kind": producer_kind,
    }

    payload: Dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "run_id": run_id,
        "phase": phase,
        "phase_id": phase_id,
        "attempt": attempt,
        "context": context,
        "producer": {
            "schema_version": _SCHEMA_VERSION,
            "name": PRODUCER_NAME,
            "version": _producer_version(),
            "instance_id": instance_id or uuid.uuid4().hex[:8],
        },
        "duration": {
            "schema_version": _SCHEMA_VERSION,
            "wall_clock_ms": float(wall_clock_ms),
        },
    }

    return {
        "schema_version": _SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "event_type": MEASUREMENT_EVENT_TYPE,
        "timestamp_iso": now.isoformat(),
        "payload": payload,
    }


def emit_phase_metrics(
    *,
    run_id: str,
    phase: str,
    wall_clock_ms: float,
    ticket_id: str = "",
    repo_id: str = "",
    model_id: str = "",
    producer_kind: str = "agent",
    phase_id: str = "",
    attempt: int = 1,
    instance_id: Optional[str] = None,
) -> bool:
    """Emit one phase measurement. Fire-and-forget; never raises.

    Returns True only when the daemon ACKs the event. A False return means the
    measurement was not queued (no daemon, timeout, broken socket) and is not
    an error the caller should act on -- hooks must never fail a session over
    telemetry.
    """
    try:
        event = build_measurement_event(
            run_id=run_id,
            phase=phase,
            wall_clock_ms=wall_clock_ms,
            ticket_id=ticket_id,
            repo_id=repo_id,
            model_id=model_id,
            producer_kind=producer_kind,
            phase_id=phase_id,
            attempt=attempt,
            instance_id=instance_id,
        )
        return send_event(EVENT_TYPE, event)
    except Exception:  # noqa: BLE001 -- telemetry must never break a session
        return False

"""Tests for .cursor/hooks/lib/measurement_emitter.py — B5 measurement parity (OMN-16598).

Shape tests run everywhere (stdlib + pytest). The SPI validation tests import
omnibase_spi's measurement contracts straight from the sibling checkout
(``../omnibase_spi/src``; pydantic only) and skip when it is absent — the same
convention as the omnimarket real-load tests in test_event_registry_tier.py.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / ".cursor" / "hooks" / "lib"
_SPI_SRC = _ROOT.parent / "omnibase_spi" / "src"
_SPI_MEASUREMENT = _SPI_SRC / "omnibase_spi" / "contracts" / "measurement"
sys.path.insert(0, str(_LIB))  # lib modules import each other by bare name


def _load(name: str, path: Path) -> Any:
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_load("emit_client", _LIB / "emit_client.py")
_mod = _load("measurement_emitter", _LIB / "measurement_emitter.py")


def _build(**overrides: Any) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "run_id": str(uuid.uuid4()),
        "phase": "implement",
        "wall_clock_ms": 1234.5,
    }
    kwargs.update(overrides)
    return _mod.build_measurement_event(**kwargs)


class TestBuildMeasurementEvent:
    def test_envelope_required_fields_present(self) -> None:
        rec = _build()
        assert set(rec) == {
            "schema_version",
            "event_id",
            "event_type",
            "timestamp_iso",
            "payload",
        }
        assert rec["event_type"] == "phase_completed"
        uuid.UUID(rec["event_id"])  # well-formed
        assert rec["timestamp_iso"].endswith("+00:00")

    def test_payload_required_fields_present(self) -> None:
        payload = _build(run_id="run-1")["payload"]
        assert payload["run_id"] == "run-1"
        assert payload["phase"] == "implement"
        assert payload["attempt"] == 1
        assert payload["duration"]["wall_clock_ms"] == 1234.5
        assert payload["producer"]["name"] == "omnicursor-hooks"
        assert payload["producer"]["instance_id"]

    def test_context_uses_native_fields_not_extensions(self) -> None:
        ctx = _build(model_id="m-1", producer_kind="agent")["payload"]["context"]
        assert ctx["toolchain"] == "cursor"
        assert ctx["producer_kind"] == "agent"
        assert ctx["model_id"] == "m-1"
        assert "extensions" not in ctx  # contract default: {}

    def test_ticket_id_present_but_empty_by_default(self) -> None:
        ctx = _build()["payload"]["context"]
        assert "ticket_id" in ctx
        assert ctx["ticket_id"] == ""

    @pytest.mark.parametrize(
        "phase", ["plan", "implement", "verify", "review", "release"]
    )
    def test_valid_phases_pass_through(self, phase: str) -> None:
        assert _build(phase=phase)["payload"]["phase"] == phase

    def test_unknown_phase_falls_back_to_implement(self) -> None:
        # Platform ruling (2026-08-31): the donor's unknown-phase default is
        # IMPLEMENT; Cursor mirrors it instead of inventing a heuristic phase.
        assert _build(phase="cursor-turn")["payload"]["phase"] == "implement"

    @pytest.mark.parametrize("kind", ["agent", "human", "unknown"])
    def test_valid_producer_kinds_pass_through(self, kind: str) -> None:
        ctx = _build(producer_kind=kind)["payload"]["context"]
        assert ctx["producer_kind"] == kind

    def test_invalid_producer_kind_falls_back_to_unknown(self) -> None:
        ctx = _build(producer_kind="robot")["payload"]["context"]
        assert ctx["producer_kind"] == "unknown"

    def test_event_ids_unique_per_call(self) -> None:
        assert _build()["event_id"] != _build()["event_id"]


class TestEmitPhaseMetrics:
    def test_emit_sends_the_registry_key_phase_metrics(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: List[Tuple[str, Dict[str, Any]]] = []

        def _capture(event_type: str, payload: Dict[str, Any]) -> bool:
            sent.append((event_type, payload))
            return True

        monkeypatch.setattr(_mod, "send_event", _capture)
        ok = _mod.emit_phase_metrics(run_id="r", phase="implement", wall_clock_ms=1.0)
        assert ok is True
        assert [event_type for event_type, _ in sent] == ["phase.metrics"]
        assert sent[0][1]["payload"]["run_id"] == "r"

    def test_emit_returns_false_when_daemon_absent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_EMIT_SOCKET", str(tmp_path / "missing.sock"))
        monkeypatch.setenv("OMNICURSOR_EMIT_TIMEOUT", "0.1")
        ok = _mod.emit_phase_metrics(run_id="r", phase="implement", wall_clock_ms=1.0)
        assert ok is False

    def test_emit_never_raises_when_the_builder_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(**_: Any) -> Dict[str, Any]:
            raise RuntimeError("boom")

        monkeypatch.setattr(_mod, "build_measurement_event", _boom)
        ok = _mod.emit_phase_metrics(run_id="r", phase="implement", wall_clock_ms=1.0)
        assert ok is False


# ---------------------------------------------------------------------------
# Real SPI contracts (sibling checkout) — skipped when omnibase_spi is absent
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _SPI_MEASUREMENT.is_dir(),
    reason="omnibase_spi sources not checked out as a sibling repo",
)
class TestSpiContractValidation:
    """The pre-daemon wire dict validates against the real contracts (extra='forbid')."""

    @pytest.fixture(autouse=True)
    def _spi(self) -> None:
        if str(_SPI_SRC) not in sys.path:
            sys.path.insert(0, str(_SPI_SRC))
        from omnibase_spi.contracts.measurement import (
            ContractMeasurementEvent,
            ContractPhaseMetrics,
        )

        self.event_model = ContractMeasurementEvent
        self.metrics_model = ContractPhaseMetrics

    def test_record_validates_as_contract_measurement_event(self) -> None:
        event = self.event_model.model_validate(_build())
        assert event.event_type == "phase_completed"

    def test_payload_validates_with_native_context_and_empty_extensions(self) -> None:
        metrics = self.metrics_model.model_validate(
            _build(producer_kind="agent")["payload"]
        )
        assert metrics.phase.value == "implement"
        assert metrics.context is not None
        assert metrics.context.toolchain == "cursor"
        assert metrics.context.producer_kind == "agent"
        assert metrics.context.extensions == {}
        assert metrics.extensions == {}

    def test_empty_ticket_id_is_accepted_by_the_contract(self) -> None:
        metrics = self.metrics_model.model_validate(_build()["payload"])
        assert metrics.context is not None
        assert metrics.context.ticket_id == ""

    def test_contract_rejects_a_producer_kind_outside_the_literal(self) -> None:
        # The emitter falls back to "unknown" precisely because the contract
        # would reject anything else.
        from pydantic import ValidationError

        record = _build()
        record["payload"]["context"]["producer_kind"] = "robot"
        with pytest.raises(ValidationError):
            self.metrics_model.model_validate(record["payload"])

"""A3 — canonical ModelCursorHookEvent builder: normalization + round-trip.

Structural tests exercise the stdlib builder directly. The round-trip tests
deserialize the built dict through the REAL backend model
(``omnibase_core.models.hooks.cursor.model_cursor_hook_event``) imported from
the sibling checkout via synthetic namespace parents — the same technique
``test_event_registry_tier.py`` uses for omnimarket — and are skipped when the
sibling (or pydantic) is absent.
"""

from __future__ import annotations

import datetime
import importlib
import importlib.util as _ilu
import sys
import types
import uuid
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / ".cursor" / "hooks" / "lib"
_CORE_SRC = _ROOT.parent / "omnibase_core" / "src"


def _load(name: str, path: Path) -> Any:
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_mod = _load("canonical_event", _LIB / "canonical_event.py")

_CANONICAL_KEYS = {
    "event_type",
    "session_id",
    "correlation_id",
    "timestamp_utc",
    "agent_source",
    "payload",
}


class TestNormalization:
    @pytest.mark.parametrize(
        ("native", "canonical"),
        [
            ("beforeSubmitPrompt", "UserPromptSubmit"),
            ("stop", "Stop"),
            ("beforeShellExecution", "PreToolUse"),
            ("afterFileEdit", "PostToolUse"),
            ("postToolUse", "PostToolUse"),
            ("sessionStart", "SessionStart"),
            ("sessionEnd", "SessionEnd"),
        ],
    )
    def test_native_names_normalize(self, native: str, canonical: str) -> None:
        assert _mod.normalize_event_name(native) == canonical

    def test_unknown_name_passes_through(self) -> None:
        assert _mod.normalize_event_name("futureHook") == "futureHook"


class TestBuildCursorEvent:
    def test_exactly_the_six_canonical_top_level_keys(self) -> None:
        event = _mod.build_cursor_event("beforeSubmitPrompt", "s-1", {"a": 1})
        assert set(event) == _CANONICAL_KEYS

    def test_agent_source_is_cursor(self) -> None:
        assert _mod.build_cursor_event("stop", "s", {})["agent_source"] == "cursor"

    def test_timestamp_is_tz_aware_iso(self) -> None:
        ts = _mod.build_cursor_event("stop", "s", {})["timestamp_utc"]
        parsed = datetime.datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_payload_nests_arbitrary_fields(self) -> None:
        payload = {"prompt": "p", "delegation_required": True, "extra": [1, 2]}
        event = _mod.build_cursor_event("beforeSubmitPrompt", "s", payload)
        assert event["payload"] == payload

    def test_none_session_id_becomes_empty_string(self) -> None:
        assert _mod.build_cursor_event("stop", None, {})["session_id"] == ""

    def test_generate_correlation_id_is_full_uuid(self) -> None:
        cid = _mod.generate_correlation_id()
        assert str(uuid.UUID(cid)) == cid


class TestCorrelationIdValidation:
    def test_valid_uuid_is_kept(self) -> None:
        cid = str(uuid.uuid4())
        event = _mod.build_cursor_event("stop", "s", {}, correlation_id=cid)
        assert event["correlation_id"] == cid

    def test_short_hex_id_drops_to_none(self) -> None:
        # Old session state may carry the legacy uuid4().hex[:12] short id,
        # which would fail backend UUID validation — drop, never ship.
        event = _mod.build_cursor_event("stop", "s", {}, correlation_id="abc123def456")
        assert event["correlation_id"] is None

    def test_empty_and_none_drop_to_none(self) -> None:
        assert _mod.build_cursor_event("stop", "s", {})["correlation_id"] is None
        assert (
            _mod.build_cursor_event("stop", "s", {}, correlation_id="")[
                "correlation_id"
            ]
            is None
        )


# ---------------------------------------------------------------------------
# Round-trip through the real backend model (sibling omnibase_core checkout)
# ---------------------------------------------------------------------------


def _load_real_cursor_model() -> Any:
    """Import ModelCursorHookEvent from the sibling omnibase_core checkout.

    Synthetic namespace parents keep the heavy package __init__ chain out of
    the picture: only the model/enum modules (pydantic + stdlib) execute —
    the exact code that validates this payload backend-side.
    """
    created = []
    for name in (
        "omnibase_core",
        "omnibase_core.enums",
        "omnibase_core.enums.hooks",
        "omnibase_core.enums.hooks.claude_code",
        "omnibase_core.enums.hooks.cursor",
        "omnibase_core.utils",
        "omnibase_core.models",
        "omnibase_core.models.hooks",
        "omnibase_core.models.hooks.claude_code",
        "omnibase_core.models.hooks.cursor",
    ):
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [str(_CORE_SRC / name.replace(".", "/"))]
            sys.modules[name] = mod
            created.append(name)
    try:
        return importlib.import_module(
            "omnibase_core.models.hooks.cursor.model_cursor_hook_event"
        )
    except Exception:
        for name in created:
            sys.modules.pop(name, None)
        raise


@pytest.mark.skipif(
    not (_CORE_SRC / "omnibase_core" / "models" / "hooks" / "cursor").is_dir(),
    reason="omnibase_core sources not checked out as a sibling repo",
)
class TestRoundTripThroughRealModel:
    def test_built_event_deserializes(self) -> None:
        m = _load_real_cursor_model()
        event = _mod.build_cursor_event(
            "beforeSubmitPrompt",
            "conv-1",
            {
                "prompt": "fix the bug",
                "matched_agent": "debug-intelligence",
                "delegation_required": False,
            },
            correlation_id=str(uuid.uuid4()),
        )
        model = m.ModelCursorHookEvent(**event)
        assert model.event_type.value == "UserPromptSubmit"
        assert model.session_id == "conv-1"
        assert model.agent_source == "cursor"
        assert model.timestamp_utc.tzinfo is not None

    def test_none_correlation_id_deserializes(self) -> None:
        m = _load_real_cursor_model()
        event = _mod.build_cursor_event("stop", "conv-2", {})
        assert m.ModelCursorHookEvent(**event).correlation_id is None

    def test_every_normalized_name_is_a_valid_enum_value(self) -> None:
        m = _load_real_cursor_model()
        enum_mod = importlib.import_module(
            "omnibase_core.enums.hooks.cursor.enum_cursor_hook_event_type"
        )
        for native in _mod._EVENT_NAME_MAP:
            event = _mod.build_cursor_event(native, "s", {})
            model = m.ModelCursorHookEvent(**event)
            assert isinstance(model.event_type, enum_mod.EnumCursorHookEventType)

    def test_stray_top_level_key_is_rejected(self) -> None:
        # extra="forbid" guard: anything non-canonical must ride inside payload.
        m = _load_real_cursor_model()
        event = _mod.build_cursor_event("stop", "s", {})
        event["matched_agent"] = "oops"
        with pytest.raises(Exception, match="matched_agent"):
            m.ModelCursorHookEvent(**event)

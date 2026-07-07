"""Registry loads with tier — config/event_registry/omnicursor.yaml.

The shared emit daemon's EventRegistry.from_yaml raises ValueError for any
fan-out rule missing a durability ``tier`` (valid: duty_critical | telemetry),
so a tier-less registry means the daemon dies at startup and every emit is
orphaned. Structural tests parse the YAML directly; the real-load tests import
the actual omnimarket ``event_registry`` module when its sources are checked
out as a sibling repo (this workspace's layout) and are skipped otherwise.

Tier assignments mirror the canonical claude_code registry
(omnimarket .../node_emit_daemon/registries/topics.yaml) for the shared keys.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY = _ROOT / "config" / "event_registry" / "omnicursor.yaml"
_OMNIMARKET_SRC = _ROOT.parent / "omnimarket" / "src"

_VALID_TIERS = {"duty_critical", "telemetry"}

# Canonical-mirrored expectations, one row per fan-out rule.
_EXPECTED_TIERS: Dict[Tuple[str, str], str] = {
    ("session.outcome", "onex.cmd.omniintelligence.session-outcome.v1"): "duty_critical",
    ("session.outcome", "onex.evt.omnicursor.session-outcome.v1"): "duty_critical",
    (
        "utilization.scoring.requested",
        "onex.cmd.omniintelligence.utilization-scoring.v1",
    ): "telemetry",
    ("prompt.submitted", "onex.evt.omnicursor.prompt-submitted.v1"): "telemetry",
    ("tool.executed", "onex.evt.omnicursor.tool-executed.v1"): "telemetry",
    ("injection.recorded", "onex.evt.omnicursor.injection-recorded.v1"): "telemetry",
}


def _registry_doc() -> Dict[str, Any]:
    return yaml.safe_load(_REGISTRY.read_text(encoding="utf-8"))


def _fan_out_rules(doc: Dict[str, Any]) -> Iterator[Tuple[str, Dict[str, Any]]]:
    for event_type, definition in doc["events"].items():
        for rule in definition["fan_out"]:
            yield event_type, rule


class TestRegistryStructure:
    def test_every_fan_out_rule_declares_a_tier(self) -> None:
        missing = [
            (event_type, rule.get("topic"))
            for event_type, rule in _fan_out_rules(_registry_doc())
            if "tier" not in rule
        ]
        assert missing == [], f"fan-out rules without tier (daemon won't load): {missing}"

    def test_every_tier_is_valid(self) -> None:
        invalid = [
            (event_type, rule["topic"], rule["tier"])
            for event_type, rule in _fan_out_rules(_registry_doc())
            if rule["tier"] not in _VALID_TIERS
        ]
        assert invalid == []

    def test_tiers_mirror_canonical_claude_code_registry(self) -> None:
        actual = {
            (event_type, rule["topic"]): rule["tier"]
            for event_type, rule in _fan_out_rules(_registry_doc())
        }
        for key, expected_tier in _EXPECTED_TIERS.items():
            assert actual.get(key) == expected_tier, key

    def test_known_event_keys_present(self) -> None:
        # PR-1 scope guard: tier-only change, no key added or removed.
        # The A3/A4 fan-out work (next PR) will extend this set deliberately.
        expected = {event_type for event_type, _ in _EXPECTED_TIERS}
        assert expected.issubset(set(_registry_doc()["events"]))


# ---------------------------------------------------------------------------
# Real-load through the actual omnimarket EventRegistry (sibling checkout)
# ---------------------------------------------------------------------------


def _load_real_event_registry() -> Any:
    """Import omnimarket's event_registry module from the sibling checkout.

    Synthetic namespace parents keep the heavy package __init__ chain (Kafka,
    omnibase_core) out of the picture: only event_registry.py and the two
    model modules it imports actually execute — the exact code that parses
    and validates this registry in the daemon.
    """
    created = []
    for name in (
        "omnimarket",
        "omnimarket.nodes",
        "omnimarket.nodes.node_emit_daemon",
        "omnimarket.nodes.node_emit_daemon.models",
    ):
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [str(_OMNIMARKET_SRC / name.replace(".", "/"))]
            sys.modules[name] = mod
            created.append(name)
    try:
        return importlib.import_module(
            "omnimarket.nodes.node_emit_daemon.event_registry"
        )
    except Exception:
        for name in created:
            sys.modules.pop(name, None)
        raise


@pytest.mark.skipif(
    not (_OMNIMARKET_SRC / "omnimarket" / "nodes" / "node_emit_daemon").is_dir(),
    reason="omnimarket sources not checked out as a sibling repo "
    "(run PHASE_0_RESULTS §6(f) from the omnimarket checkout instead)",
)
class TestRealEventRegistryLoad:
    def test_registry_loads_under_daemon_parser(self) -> None:
        er = _load_real_event_registry()
        registry = er.EventRegistry.from_yaml(_REGISTRY)
        assert len(registry) == len(_registry_doc()["events"])
        for (event_type, topic), expected_tier in _EXPECTED_TIERS.items():
            registration = registry.get_registration(event_type)
            tiers = {rule.topic: rule.tier.value for rule in registration.fan_out}
            assert tiers[topic] == expected_tier

    def test_missing_tier_raises_value_error(self, tmp_path: Path) -> None:
        doc = _registry_doc()
        first_key = next(iter(doc["events"]))
        del doc["events"][first_key]["fan_out"][0]["tier"]
        stripped = tmp_path / "omnicursor-no-tier.yaml"
        stripped.write_text(yaml.safe_dump(doc), encoding="utf-8")

        er = _load_real_event_registry()
        with pytest.raises(ValueError, match="tier"):
            er.EventRegistry.from_yaml(stripped)

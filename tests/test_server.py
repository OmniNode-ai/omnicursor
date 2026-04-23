"""Public Python API for agents, skills, and compliance (used by tests and scripts)."""

from __future__ import annotations

from omnicursor.agents import get_agent_context
from omnicursor.compliance import check_compliance
from omnicursor.skills import SkillRepository


def _skill_payload(skill_name: str) -> dict:
    return SkillRepository().load_skill(skill_name).model_dump(mode="json")


def test_get_agent_context_returns_debugging_profile() -> None:
    payload = get_agent_context("debugging").model_dump(mode="json")

    assert payload["agent_name"] == "systematic-debugger"
    assert payload["recommended_skill"] == "systematic-debugging"


def test_get_agent_context_returns_brainstorming_profile() -> None:
    payload = get_agent_context("brainstorming").model_dump(mode="json")

    assert payload["agent_name"] == "brainstorming-guide"
    assert payload["recommended_skill"] == "brainstorming"


def test_invoke_skill_loads_markdown_skill() -> None:
    payload = _skill_payload("systematic-debugging")

    assert payload["skill_name"] == "systematic-debugging"
    assert payload["path"] == ".cursor/skills/systematic-debugging/SKILL.md"


def test_invoke_skill_loads_brainstorming_skill() -> None:
    payload = _skill_payload("brainstorming")

    assert payload["skill_name"] == "brainstorming"
    assert payload["path"] == ".cursor/skills/brainstorming/SKILL.md"


def test_check_compliance_returns_result() -> None:
    payload = check_compliance(
        "systematic-debugging",
        "The symptom was an error. The cause is a bug. The fix updates the code. Run tests to verify.",
    ).model_dump(mode="json")

    assert payload["skill_name"] == "systematic-debugging"
    assert payload["compliant"] is True
    assert payload["missing"] == []


def test_check_compliance_detects_missing() -> None:
    payload = check_compliance(
        "systematic-debugging",
        "There was an error. I think the cause is X.",
    ).model_dump(mode="json")

    assert payload["compliant"] is False
    assert "suggests_minimal_fix" in payload["missing"]

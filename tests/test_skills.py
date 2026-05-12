from pathlib import Path

import pytest

from omnicursor.skills import SkillRepository

_REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def repository() -> SkillRepository:
    return SkillRepository()


def test_load_systematic_debugging_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("systematic-debugging")
    assert skill.skill_name == "systematic-debugging"
    assert skill.path == ".cursor/skills/systematic-debugging/SKILL.md"
    assert "Systematic Debugging" in skill.content


def test_load_brainstorming_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("brainstorming")
    assert skill.skill_name == "brainstorming"
    assert skill.path == ".cursor/skills/brainstorming/SKILL.md"
    assert "Brainstorming" in skill.content


def test_load_writing_plans_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("writing-plans")
    assert skill.skill_name == "writing-plans"
    assert skill.path == ".cursor/skills/writing-plans/SKILL.md"
    assert "Writing Plans" in skill.content


def test_load_plan_ticket_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("plan-ticket")
    assert skill.skill_name == "plan-ticket"
    assert skill.path == ".cursor/skills/plan-ticket/SKILL.md"
    assert "Plan Ticket" in skill.content


def test_available_skills_lists_all(repository: SkillRepository) -> None:
    available = repository.available_skills()
    expected = [
        "brainstorming",
        "defense-in-depth",
        "execute-plan",
        "handoff",
        "hostile-reviewer",
        "insights-to-plan",
        "merge-planner",
        "plan-review",
        "plan-ticket",
        "plan-to-tickets",
        "pr-polish",
        "pr-review",
        "recap",
        "systematic-debugging",
        "using-git-worktrees",
        "writing-plans",
    ]
    assert available == expected


def test_load_recap_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("recap")
    assert skill.skill_name == "recap"
    assert skill.path == ".cursor/skills/recap/SKILL.md"
    assert "Session Recap" in skill.content


def test_load_plan_review_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("plan-review")
    assert skill.skill_name == "plan-review"
    assert skill.path == ".cursor/skills/plan-review/SKILL.md"
    assert "Plan Review" in skill.content


def test_load_plan_to_tickets_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("plan-to-tickets")
    assert skill.skill_name == "plan-to-tickets"
    assert skill.path == ".cursor/skills/plan-to-tickets/SKILL.md"
    assert "Plan to Tickets" in skill.content


def test_load_execute_plan_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("execute-plan")
    assert skill.skill_name == "execute-plan"
    assert skill.path == ".cursor/skills/execute-plan/SKILL.md"
    assert "execute-plan" in skill.content


def test_load_nonexistent_skill_raises(repository: SkillRepository) -> None:
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        repository.load_skill("nonexistent")


def test_skills_dual_path_parity() -> None:
    """skills/*.md and .cursor/skills/*/SKILL.md must have identical content."""
    canonical_dir = _REPO / "skills"
    cursor_dir = _REPO / ".cursor" / "skills"
    mismatches = []
    for canonical in sorted(canonical_dir.glob("*.md")):
        if canonical.stem.upper() == "README":
            continue
        name = canonical.stem
        cursor_copy = cursor_dir / name / "SKILL.md"
        if not cursor_copy.exists():
            mismatches.append(f"{name}: .cursor/skills/{name}/SKILL.md missing")
            continue
        if canonical.read_text(encoding="utf-8") != cursor_copy.read_text(encoding="utf-8"):
            mismatches.append(f"{name}: skills/{name}.md and .cursor/skills/{name}/SKILL.md differ")
    assert not mismatches, "Skill dual-path divergence:\n" + "\n".join(mismatches)

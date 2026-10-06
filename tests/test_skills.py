import re
from pathlib import Path

import pytest
import yaml

from omnicursor.skills import SkillRepository, canonical_skill_id

_REPO = Path(__file__).resolve().parents[1]

_FRONT_MATTER_BOUNDARY = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def _skill_markdown_without_frontmatter(content: str) -> str:
    m = _FRONT_MATTER_BOUNDARY.match(content)
    return content[m.end() :] if m else content


@pytest.fixture
def repository() -> SkillRepository:
    return SkillRepository()


def test_load_systematic_debugging_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("systematic-debugging")
    assert skill.skill_name == "onex-systematic-debugging"
    assert skill.path == "skills/onex-systematic-debugging/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-systematic-debugging\n"
    )


def test_load_brainstorming_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("brainstorming")
    assert skill.skill_name == "onex-brainstorming"
    assert skill.path == "skills/onex-brainstorming/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-brainstorming\n"
    )


def test_load_writing_plans_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("writing-plans")
    assert skill.skill_name == "onex-writing-plans"
    assert skill.path == "skills/onex-writing-plans/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-writing-plans\n"
    )


def test_load_plan_ticket_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("plan-ticket")
    assert skill.skill_name == "onex-plan-ticket"
    assert skill.path == "skills/onex-plan-ticket/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-plan-ticket\n"
    )


def test_load_docs_reality_sync_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("docs-reality-sync")
    assert skill.skill_name == "onex-docs-reality-sync"
    assert skill.path == "skills/onex-docs-reality-sync/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-docs-reality-sync\n"
    )


def test_available_skills_lists_all(repository: SkillRepository) -> None:
    available = repository.available_skills()
    expected = [
        "onex-brainstorming",
        "onex-defense-in-depth",
        "onex-docs-reality-sync",
        "onex-execute-plan",
        "onex-handoff",
        "onex-hostile-reviewer",
        "onex-insights-to-plan",
        "onex-merge-planner",
        "onex-plan-review",
        "onex-plan-ticket",
        "onex-plan-to-tickets",
        "onex-pr-polish",
        "onex-pr-review",
        "onex-recap",
        "onex-systematic-debugging",
        "onex-using-git-worktrees",
        "onex-writing-plans",
    ]
    assert available == expected


def test_load_recap_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("recap")
    assert skill.skill_name == "onex-recap"
    assert skill.path == "skills/onex-recap/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-recap\n"
    )


def test_load_plan_review_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("plan-review")
    assert skill.skill_name == "onex-plan-review"
    assert skill.path == "skills/onex-plan-review/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-plan-review\n"
    )


def test_load_plan_to_tickets_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("plan-to-tickets")
    assert skill.skill_name == "onex-plan-to-tickets"
    assert skill.path == "skills/onex-plan-to-tickets/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-plan-to-tickets\n"
    )


def test_load_execute_plan_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("execute-plan")
    assert skill.skill_name == "onex-execute-plan"
    assert skill.path == "skills/onex-execute-plan/SKILL.md"
    assert _skill_markdown_without_frontmatter(skill.content).startswith(
        "# onex-execute-plan\n"
    )


def test_all_skills_cursor_frontmatter_onex_namespace() -> None:
    canonical_dir = _REPO / "skills"
    for path in sorted(canonical_dir.glob("*/SKILL.md")):
        if path.stem.upper() == "README":
            continue
        raw = path.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
        assert m is not None, f"missing YAML frontmatter: {path}"
        fm = yaml.safe_load(m.group(1))
        assert fm is not None and isinstance(fm, dict), path
        name = fm.get("name")
        assert name == path.parent.name, f"name mismatch in {path}: {name!r}"
        description = fm.get("description")
        assert description, f"missing description in {path}"
        # A truthy-but-degenerate value like "---" (a folded scalar swallowing
        # the frontmatter terminator — the historical hostile-reviewer bug)
        # must not pass as a real description.
        assert isinstance(description, str) and len(description.strip("- \n")) >= 10, (
            f"degenerate description in {path}: {description!r}"
        )
        assert fm.get("disable-model-invocation") is True, path


def test_load_skill_accepts_legacy_colon_id(repository: SkillRepository) -> None:
    skill = repository.load_skill("onex" + ":brainstorming")
    assert skill.skill_name == "onex-brainstorming"


def test_load_skill_accepts_canonical_id(repository: SkillRepository) -> None:
    skill = repository.load_skill("onex-brainstorming")
    assert skill.skill_name == "onex-brainstorming"


def test_load_nonexistent_skill_raises(repository: SkillRepository) -> None:
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        repository.load_skill("nonexistent")


def test_skills_have_one_canonical_location() -> None:
    from omnicursor.compliance import COMPLIANCE_REGISTRY

    paths = list((_REPO / "skills").glob("*/SKILL.md"))
    assert {p.parent.name for p in paths} == set(COMPLIANCE_REGISTRY)
    assert len(paths) == 17
    assert not (_REPO / ".cursor" / "skills").exists()
    assert list((_REPO / "skills").glob("*.md")) == [_REPO / "skills/README.md"]
    for path in paths:
        assert canonical_skill_id(path.parent.name) == path.parent.name

"""Local skill loading for OmniCursor."""

from __future__ import annotations

from pathlib import Path
from typing import List

from .db import REPO_ROOT, SKILLS_DIR
from .schemas import SkillDocument


class SkillRepository:
    """Load skills from .cursor/skills/<name>/SKILL.md (Cursor-native format)."""

    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self.skills_dir = skills_dir

    def available_skills(self) -> List[str]:
        """Return sorted list of skill names (directory names containing SKILL.md)."""
        if not self.skills_dir.is_dir():
            return []
        return sorted(
            d.name
            for d in self.skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )

    def resolve_path(self, skill_name: str) -> Path:
        return self.skills_dir / skill_name / "SKILL.md"

    def load_skill(self, skill_name: str) -> SkillDocument:
        path = self.resolve_path(skill_name)
        if not path.exists():
            available = ", ".join(self.available_skills()) or "(none)"
            raise FileNotFoundError(
                f"Skill '{skill_name}' was not found in {self.skills_dir}. "
                f"Available skills: {available}"
            )

        return SkillDocument(
            skill_name=skill_name,
            path=str(path.relative_to(REPO_ROOT)),
            content=path.read_text(encoding="utf-8"),
        )


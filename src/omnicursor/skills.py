"""Local skill loading for OmniCursor."""

from __future__ import annotations

from pathlib import Path
from typing import List

from .db import REPO_ROOT, SKILLS_DIR
from .schemas import SkillDocument

# Human-facing skill IDs in this repo use an ONEX-style namespace prefix.
# Cursor slash-picker labels follow subfolder names, so dirs use ``onex-<slug>``.
# ``skill_slug()`` still strips legacy ``onex:`` and ``onex-`` prefixes to bare slug.
SKILL_ID_PREFIX = "onex-"

# Legacy colon form (disallowed in Cursor skill frontmatter `name` fields).
_LEGACY_COLON_PREFIX = "onex" + ":"


def skill_slug(skill_name: str) -> str:
    """Return filesystem slug for a skill.

    Accepts legacy colon-delimited skill ids (namespace ``onex`` immediately
    followed by ``:`` and ``<slug>``) plus current hyphenated ``onex-<slug>``
    canonical ids or bare filesystem slugs.
    """
    s = skill_name.strip()
    if s.startswith(_LEGACY_COLON_PREFIX):
        return s[len(_LEGACY_COLON_PREFIX) :]
    if s.startswith(SKILL_ID_PREFIX):
        return s[len(SKILL_ID_PREFIX) :]
    return s


def canonical_skill_id(skill_name: str) -> str:
    """Return the canonical registry / API id: ``onex-<slug>``."""
    return f"{SKILL_ID_PREFIX}{skill_slug(skill_name)}"


class SkillRepository:
    """Load skills from ``.cursor/skills/onex-<slug>/SKILL.md`` (Cursor-native format)."""

    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self.skills_dir = skills_dir

    def available_skills(self) -> List[str]:
        """Return sorted list of canonical skill ids (onex-<slug>) for each SKILL.md dir."""
        if not self.skills_dir.is_dir():
            return []
        return sorted(
            canonical_skill_id(d.name)
            for d in self.skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )

    def resolve_path(self, skill_name: str) -> Path:
        return self.skills_dir / canonical_skill_id(skill_name) / "SKILL.md"

    def load_skill(self, skill_name: str) -> SkillDocument:
        cid = canonical_skill_id(skill_name)
        path = self.skills_dir / cid / "SKILL.md"
        if not path.exists():
            available = ", ".join(self.available_skills()) or "(none)"
            raise FileNotFoundError(
                f"Skill '{skill_name}' was not found in {self.skills_dir}. "
                f"Available skills: {available}"
            )

        return SkillDocument(
            skill_name=cid,
            path=str(path.relative_to(REPO_ROOT)),
            content=path.read_text(encoding="utf-8"),
        )

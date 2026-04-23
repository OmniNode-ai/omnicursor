"""Shared repo paths and v1 storage placeholders."""

from __future__ import annotations

from pathlib import Path

from .schemas import DatabaseStatus


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".cursor" / "skills"
RULES_DIR = REPO_ROOT / ".cursor" / "rules"


class InMemoryDatabase:
    """Very small placeholder until real persistence is added."""

    def healthcheck(self) -> DatabaseStatus:
        return DatabaseStatus(backend="memory", status="ok")


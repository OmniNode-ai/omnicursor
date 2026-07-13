"""Pydantic schemas for the OmniCursor Python library (agents, skills, smoke-check)."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Minimal routing context returned to Cursor rules."""

    agent_name: str
    description: str = ""
    instructions: List[str] = Field(default_factory=list)
    recommended_skill: Optional[str] = None


class SkillDocument(BaseModel):
    """A local Markdown skill loaded from the repository."""

    skill_name: str
    path: str
    content: str


class ComplianceResult(BaseModel):
    """Result of a skill vocabulary smoke-check (keyword presence, not behavioral compliance)."""

    skill_name: str
    checks: Dict[str, bool]
    compliant: bool
    missing: List[str]


class PatternRecord(BaseModel):
    """Minimal pattern description for preserved starter-kit assets."""

    name: str
    description: str
    source: str


class DatabaseStatus(BaseModel):
    """Simple health structure for the v1 in-memory placeholder."""

    backend: str
    status: str

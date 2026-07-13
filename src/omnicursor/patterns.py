"""Pattern helpers backed by preserved starter-kit rule files."""

from __future__ import annotations

from typing import List

from .db import RULES_DIR
from .schemas import PatternRecord


def list_preserved_patterns() -> List[PatternRecord]:
    """Expose preserved rule assets as the first pattern catalog."""

    return [
        PatternRecord(
            name="brainstorming",
            description="Preserved idea-to-design Cursor rule.",
            source=str(RULES_DIR / "10-brainstorming.mdc"),
        ),
        PatternRecord(
            name="writing-plans",
            description="Preserved design-to-plan Cursor rule.",
            source=str(RULES_DIR / "11-writing-plans.mdc"),
        ),
        PatternRecord(
            name="plan-ticket",
            description="Preserved bounded repo-detection and ticket template rule.",
            source=str(RULES_DIR / "12-plan-ticket.mdc"),
        ),
    ]

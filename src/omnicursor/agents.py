"""Routing contexts used by the OmniCursor MCP tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schemas import AgentContext


# ---------------------------------------------------------------------------
# Repo root / agents directory
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_DIR = _REPO_ROOT / ".cursor" / "agents"


# ---------------------------------------------------------------------------
# Default (generalist) context — never changes
# ---------------------------------------------------------------------------

DEFAULT_CONTEXT = AgentContext(
    agent_name="omnicursor-generalist",
    description="General-purpose fallback agent for unmatched categories.",
    instructions=[
        "Prefer the preserved Cursor rules before inventing a new workflow.",
        "Use MCP tools only to add routing context or load a local skill.",
        "Check 00-omninode-concepts for shared vocabulary.",
    ],
    recommended_skill=None,
)


# ---------------------------------------------------------------------------
# Hardcoded agent contexts (v1 fallback — always present)
# ---------------------------------------------------------------------------

AGENT_CONTEXTS: Dict[str, AgentContext] = {
    "debugging": AgentContext(
        agent_name="systematic-debugger",
        description="Structured debugging agent — reproduce, hypothesize, verify.",
        instructions=[
            "Keep 00-omninode-concepts and 01-codebase-research as the always-on base.",
            "Reproduce the issue before editing whenever a repro is available.",
            "Load the systematic-debugging skill and follow it step-by-step.",
            "Prefer the smallest verified fix over a redesign.",
        ],
        recommended_skill="systematic-debugging",
    ),
    "brainstorming": AgentContext(
        agent_name="brainstorming-guide",
        description="Collaborative idea refinement agent — one question at a time, 2-3 approaches, design doc output.",
        instructions=[
            "Reuse the preserved 10-brainstorming rule as the primary methodology.",
            "Keep research bounded with 01-codebase-research.",
            "Ask one question per message — never combine two questions.",
            "Present 2-3 approaches with named trade-offs before settling.",
            "Write design outputs to docs/plans/ using the existing handoff protocol.",
        ],
        recommended_skill="brainstorming",
    ),
    "planning": AgentContext(
        agent_name="plan-writer",
        description="Implementation plan writer — bite-sized TDD tasks with exact file paths.",
        instructions=[
            "Reuse the preserved 11-writing-plans rule as the primary methodology.",
            "Keep tasks small, explicit, and artifact-path anchored.",
            "Each step is one action, 2-5 minutes of work.",
            "Use the preserved adversarial review structure (R1-R6) before handing off.",
            "Output complete code examples, not placeholders.",
        ],
        recommended_skill="writing-plans",
    ),
    "ticketing": AgentContext(
        agent_name="ticket-planner",
        description="Ticket contract generator — deterministic repo detection and YAML template output.",
        instructions=[
            "Reuse the preserved 12-plan-ticket rule for deterministic repo detection.",
            "Follow the 3-priority chain: CWD/prompt, README, ask user.",
            "Keep output YAML-only and use the documented handoff to the linear rule.",
            "Pre-fill fields from prompt context; mark uncertain fields as FILL IN.",
        ],
        recommended_skill="plan-ticket",
    ),
    "adapter": AgentContext(
        agent_name="adapter-guide",
        description="Bucket 3 adapter stub agent — dry-run protocol and fail-soft behavior.",
        instructions=[
            "Reuse the preserved 20-adapter-stub rule for Bucket 3 dry-run behavior.",
            "Always call dry_run: true first; never skip.",
            "Do not skip the fail-soft contract described in docs/ARCHITECTURE.md.",
            "Output complete request payloads for review, never execute live calls.",
        ],
        recommended_skill="adapter-stub",
    ),
}


# ---------------------------------------------------------------------------
# Aliases — maps shorthand names to canonical category keys
# ---------------------------------------------------------------------------

ALIASES: Dict[str, str] = {
    # Original v1 aliases
    "debug": "debugging",
    "bug": "debugging",
    "systematic-debugging": "debugging",
    "brainstorm": "brainstorming",
    "idea": "brainstorming",
    "design": "brainstorming",
    "writing-plans": "planning",
    "plan": "planning",
    "plans": "planning",
    "plan-ticket": "ticketing",
    "ticket": "ticketing",
    "tickets": "ticketing",
    "adapter-stub": "adapter",
    "bucket-3": "adapter",
    "stub": "adapter",
    # New aliases for JSON-loaded categories
    "debug-intelligence": "debug-intelligence",
    "version-control": "version-control",
    "git": "version-control",
    "commit": "version-control",
    "research": "research",
    "investigate": "research",
    "test": "testing",
    "tests": "testing",
    "testing": "testing",
    "quality": "quality",
    "code-quality": "quality",
    "lint": "quality",
    "review": "review",
    "pr": "review",
    "pull-request": "review",
    "docs": "documentation",
    "documentation": "documentation",
    "security": "security",
    "audit": "security",
    "vulnerability": "security",
    "performance": "performance",
    "optimize": "performance",
    "benchmark": "performance",
    "database": "database",
    "db": "database",
    "sql": "database",
    "frontend": "frontend",
    "react": "frontend",
    "ui": "frontend",
    "backend": "backend",
    "fastapi": "backend",
    "summarize": "summarization",
    "summarization": "summarization",
    "condense": "summarization",
    "exploration": "exploration",
    "crawl": "exploration",
    "generalist": "generalist",
}


# ---------------------------------------------------------------------------
# Dynamic JSON loading
# ---------------------------------------------------------------------------


def _load_json_agents() -> Dict[str, AgentContext]:
    """Load agent configs from .cursor/agents/*.json files.

    Returns a dict keyed by the ``category`` field in each JSON file.
    Returns ``{}`` on any failure so the hardcoded fallback always works.
    """
    result: Dict[str, AgentContext] = {}
    try:
        if not _AGENTS_DIR.is_dir():
            return result
        for path in sorted(_AGENTS_DIR.glob("*.json")):
            try:
                raw: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
                category = raw.get("category", "")
                if not category:
                    continue
                result[category] = AgentContext(
                    agent_name=raw.get("name", path.stem),
                    description=raw.get("description", ""),
                    instructions=raw.get("instructions", []),
                    recommended_skill=raw.get("recommended_skill"),
                )
            except (json.JSONDecodeError, OSError, TypeError):
                continue
    except OSError:
        pass
    return result


# Merged registry: hardcoded first, then JSON overlay
_JSON_AGENTS: Dict[str, AgentContext] = _load_json_agents()

_MERGED_CONTEXTS: Dict[str, AgentContext] = {**AGENT_CONTEXTS, **_JSON_AGENTS}

# Also store raw JSON data for match_agent trigger scoring
_RAW_JSON_AGENTS: List[Dict[str, Any]] = []
try:
    if _AGENTS_DIR.is_dir():
        for _p in sorted(_AGENTS_DIR.glob("*.json")):
            try:
                _RAW_JSON_AGENTS.append(json.loads(_p.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
except OSError:
    pass


# ---------------------------------------------------------------------------
# Category normalization
# ---------------------------------------------------------------------------


def normalize_category(category: str) -> str:
    """Normalize free-form categories to the routing table."""
    normalized = category.strip().lower().replace("_", "-")
    return ALIASES.get(normalized, normalized)


# ---------------------------------------------------------------------------
# Category-based lookup (original API — backward compatible)
# ---------------------------------------------------------------------------


def get_agent_context(category: str) -> AgentContext:
    """Return a structured context object for a rule-selected category."""
    normalized = normalize_category(category)
    return _MERGED_CONTEXTS.get(normalized, DEFAULT_CONTEXT)


# ---------------------------------------------------------------------------
# Prompt-based matching (new API)
# ---------------------------------------------------------------------------


def _score_agent(prompt_lower: str, agent: Dict[str, Any]) -> float:
    """Score a single agent config against the lowered prompt."""
    activation = agent.get("activation_patterns", {})
    explicit: List[str] = activation.get("explicit_triggers", [])
    context: List[str] = activation.get("context_triggers", [])

    max_points = 2 * len(explicit) + len(context)
    if max_points == 0:
        return 0.0

    points = 0
    for trigger in explicit:
        if trigger.lower() in prompt_lower:
            points += 2
    for trigger in context:
        if trigger.lower() in prompt_lower:
            points += 1

    return points / max_points


def match_agent(prompt: str) -> AgentContext:
    """Match a prompt to the best agent using trigger keyword scoring.

    Uses the JSON agent configs loaded from ``.cursor/agents/*.json``.
    Falls back to ``DEFAULT_CONTEXT`` if no agent scores above 0.
    """
    if not prompt or not _RAW_JSON_AGENTS:
        return DEFAULT_CONTEXT

    prompt_lower = prompt.lower()
    best_score = 0.0
    best_category: Optional[str] = None

    for agent in _RAW_JSON_AGENTS:
        score = _score_agent(prompt_lower, agent)
        if score > best_score:
            best_score = score
            best_category = agent.get("category", "")

    if best_category:
        return _MERGED_CONTEXTS.get(best_category, DEFAULT_CONTEXT)

    return DEFAULT_CONTEXT

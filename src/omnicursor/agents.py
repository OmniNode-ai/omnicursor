"""Agent routing contexts for OmniCursor (library + tests)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Set, Tuple

from .schemas import AgentContext

__all__ = [
    "AGENT_CONTEXTS",
    "ALIASES",
    "DEFAULT_CONTEXT",
    "HARD_FLOOR",
    "get_agent_context",
    "list_agents",
    "match_agent",
    "match_agent_candidates",
    "normalize_category",
    "reload_agents",
]


# ---------------------------------------------------------------------------
# Scoring engine — loaded from .cursor/hooks/lib/agent_scoring.py
#
# The canonical implementation is stdlib-only and lives next to the Cursor
# hook library.  Hooks import it directly; this module loads it by path so
# omnicursor never becomes a hook dependency, while pytest and library
# callers still use ``import omnicursor``.  Same pattern as prompt_pattern_read.py.
# ---------------------------------------------------------------------------

def _load_agent_scoring() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / ".cursor" / "hooks" / "lib" / "agent_scoring.py"
    if not path.is_file():
        raise RuntimeError(
            "agent_scoring.py not found at {}; full OmniCursor checkout required. "
            "See docs/dev/ROUTING_DEDUPLICATION.md.".format(path)
        )
    name = "_omnicursor_hook_agent_scoring"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load agent_scoring from {}".format(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_as = _load_agent_scoring()

# Re-export canonical constants and functions under their original private names
# so callers in this module and in tests are unaffected.
HARD_FLOOR: float = _as.HARD_FLOOR
_STOPWORDS: frozenset[str] = _as.STOPWORDS
_score_agent = _as.score_agent
_fuzzy_threshold = _as.fuzzy_threshold


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
        "Read skills under skills/ when needed; use hook routing hints when present.",
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
    "pr-review": "review",
    "session-handoff": "handoff",
    "continuity": "handoff",
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
# Synthetic activation patterns for hardcoded agents
# ---------------------------------------------------------------------------

def _build_hardcoded_raw_agents() -> List[Dict[str, Any]]:
    """Build raw agent dicts for hardcoded AGENT_CONTEXTS using ALIASES as triggers.

    This lets match_agent_candidates score hardcoded agents alongside JSON ones,
    closing the gap where prompts like "write me a plan" matched nothing.
    """
    # Reverse ALIASES: category -> list of alias keys that point to it
    reverse: Dict[str, List[str]] = {}
    for alias, category in ALIASES.items():
        reverse.setdefault(category, []).append(alias)

    result = []
    for category, ctx in AGENT_CONTEXTS.items():
        triggers = sorted({category} | set(reverse.get(category, [])))
        result.append({
            "name": ctx.agent_name,
            "category": category,
            "activation_patterns": {
                "explicit_triggers": triggers,
                "context_triggers": [],
                "activation_keywords": triggers,
            },
        })
    return result


_HARDCODED_RAW_AGENTS: List[Dict[str, Any]] = _build_hardcoded_raw_agents()

# JSON categories that have their own file — these shadow the hardcoded entries.
_JSON_CATEGORIES: Set[str] = {a.get("category", "") for a in _RAW_JSON_AGENTS}

# Combined scoring pool: JSON agents first; hardcoded only where JSON doesn't already cover.
_ALL_RAW_AGENTS: List[Dict[str, Any]] = _RAW_JSON_AGENTS + [
    a for a in _HARDCODED_RAW_AGENTS
    if a.get("category", "") not in _JSON_CATEGORIES
]


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


def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from *text*, filtering stopwords."""
    return _as.extract_keywords(text)


# _fuzzy_threshold and _score_agent are re-exported from the scoring engine
# at the top of this module (assigned from _as).  The functions below use them
# via those module-level names so callers are unaffected.


def match_agent_candidates(
    prompt: str,
    *,
    max_results: int = 5,
) -> List[Tuple[str, float, str]]:
    """Match a prompt against all agents using multi-strategy scoring.

    Scores both JSON agents and hardcoded AGENT_CONTEXTS (via synthesized
    activation patterns). Returns ``(category, score, reason)`` tuples sorted
    by descending score. Only candidates at or above ``HARD_FLOOR`` included.
    """
    if not prompt:
        return []

    prompt_lower = prompt.lower()
    prompt_words = set(_extract_keywords(prompt))
    candidates: List[Tuple[str, float, str]] = []

    for agent in _ALL_RAW_AGENTS:
        category = agent.get("category", "")
        if not category:
            continue
        score, reason = _score_agent(prompt_lower, prompt_words, agent)
        if score >= HARD_FLOOR:
            candidates.append((category, score, reason))

    candidates.sort(key=lambda c: c[1], reverse=True)
    return candidates[:max_results]


def match_agent(prompt: str) -> AgentContext:
    """Match a prompt to the best agent using multi-strategy scoring.

    Considers all agents (JSON + hardcoded). Falls back to ``DEFAULT_CONTEXT``
    if no agent exceeds ``HARD_FLOOR``.
    """
    candidates = match_agent_candidates(prompt)
    if candidates:
        best_category = candidates[0][0]
        return _MERGED_CONTEXTS.get(best_category, DEFAULT_CONTEXT)
    return DEFAULT_CONTEXT


def list_agents() -> List[str]:
    """Return sorted list of all known agent names across JSON and hardcoded sources."""
    return sorted({ctx.agent_name for ctx in _MERGED_CONTEXTS.values()})


def reload_agents() -> None:
    """Reload JSON agents from disk and rebuild the merged scoring pool.

    Useful in tests or after adding new ``.cursor/agents/*.json`` files without
    restarting the process.
    """
    global _JSON_AGENTS, _RAW_JSON_AGENTS, _JSON_CATEGORIES, _ALL_RAW_AGENTS, _MERGED_CONTEXTS

    _JSON_AGENTS = _load_json_agents()
    _RAW_JSON_AGENTS = []
    try:
        if _AGENTS_DIR.is_dir():
            for _p in sorted(_AGENTS_DIR.glob("*.json")):
                try:
                    _RAW_JSON_AGENTS.append(json.loads(_p.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    continue
    except OSError:
        pass

    _JSON_CATEGORIES = {a.get("category", "") for a in _RAW_JSON_AGENTS}
    _ALL_RAW_AGENTS = _RAW_JSON_AGENTS + [
        a for a in _HARDCODED_RAW_AGENTS
        if a.get("category", "") not in _JSON_CATEGORIES
    ]
    _MERGED_CONTEXTS = {**AGENT_CONTEXTS, **_JSON_AGENTS}

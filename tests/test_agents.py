from omnicursor.agents import (
    get_agent_context,
    match_agent,
    normalize_category,
    AGENT_CONTEXTS,
    DEFAULT_CONTEXT,
    _load_json_agents,
    _MERGED_CONTEXTS,
)


def test_debugging_category() -> None:
    ctx = get_agent_context("debugging")
    assert ctx.agent_name == "systematic-debugger"
    assert ctx.recommended_skill == "onex-systematic-debugging"
    assert ctx.description != ""


def test_brainstorming_category() -> None:
    ctx = get_agent_context("brainstorming")
    assert ctx.agent_name == "brainstorming-guide"
    assert ctx.recommended_skill == "onex-brainstorming"
    assert ctx.description != ""


def test_planning_category() -> None:
    ctx = get_agent_context("planning")
    assert ctx.agent_name == "plan-writer"
    assert ctx.recommended_skill == "onex-writing-plans"
    assert ctx.description != ""


def test_ticketing_category() -> None:
    ctx = get_agent_context("ticketing")
    assert ctx.agent_name == "ticket-planner"
    assert ctx.recommended_skill == "onex-plan-ticket"
    assert ctx.description != ""


def test_fallback_for_unknown_category() -> None:
    ctx = get_agent_context("unknown-category")
    assert ctx.agent_name == "omnicursor-generalist"
    assert ctx.recommended_skill is None
    assert ctx.description != ""


def test_alias_debug_routes_to_debugging() -> None:
    ctx = get_agent_context("debug")
    assert ctx.agent_name == "systematic-debugger"


def test_alias_brainstorm_routes_to_brainstorming() -> None:
    ctx = get_agent_context("brainstorm")
    assert ctx.agent_name == "brainstorming-guide"


def test_alias_plan_routes_to_planning() -> None:
    ctx = get_agent_context("plan")
    assert ctx.agent_name == "plan-writer"


def test_alias_ticket_routes_to_ticketing() -> None:
    ctx = get_agent_context("ticket")
    assert ctx.agent_name == "ticket-planner"


def test_all_four_categories_present() -> None:
    expected = {"debugging", "brainstorming", "planning", "ticketing"}
    assert set(AGENT_CONTEXTS.keys()) == expected


# ---------------------------------------------------------------------------
# Phase 3A: dynamic JSON loading + match_agent
# ---------------------------------------------------------------------------


def test_load_json_agents_returns_dict() -> None:
    result = _load_json_agents()
    assert isinstance(result, dict)
    assert len(result) > 0
    for key, value in result.items():
        assert isinstance(key, str)
        assert hasattr(value, "agent_name")


def test_load_json_agents_returns_empty_when_dir_missing(tmp_path, monkeypatch) -> None:
    import omnicursor.agents as agents_mod

    monkeypatch.setattr(agents_mod, "_AGENTS_DIR", tmp_path / "nonexistent")
    result = agents_mod._load_json_agents()
    assert result == {}


def test_merged_contexts_includes_hardcoded_and_json() -> None:
    # Hardcoded categories that don't collide with JSON
    assert "brainstorming" in _MERGED_CONTEXTS
    assert "planning" in _MERGED_CONTEXTS
    assert "ticketing" in _MERGED_CONTEXTS
    # JSON-only categories
    assert "version-control" in _MERGED_CONTEXTS
    assert "research" in _MERGED_CONTEXTS
    assert "testing" in _MERGED_CONTEXTS


def test_match_agent_debug_prompt() -> None:
    ctx = match_agent("debug this failing test")
    assert ctx.agent_name != "omnicursor-generalist"
    assert ctx.agent_name != ""


def test_match_agent_testing_prompt() -> None:
    ctx = match_agent("write tests for the new endpoint")
    assert ctx.agent_name == "testing"


def test_match_agent_unrelated_prompt_returns_default() -> None:
    ctx = match_agent("random text about cooking")
    assert ctx.agent_name == DEFAULT_CONTEXT.agent_name


def test_match_agent_empty_prompt_returns_default() -> None:
    ctx = match_agent("")
    assert ctx.agent_name == DEFAULT_CONTEXT.agent_name


def test_get_agent_context_debugging_still_works() -> None:
    ctx = get_agent_context("debugging")
    assert ctx.agent_name != ""
    assert ctx.recommended_skill == "onex-systematic-debugging"


def test_get_agent_context_brainstorming_still_works() -> None:
    ctx = get_agent_context("brainstorming")
    assert ctx.agent_name == "brainstorming-guide"


def test_normalize_category_bug_returns_debugging() -> None:
    assert normalize_category("bug") == "debugging"


def test_normalize_category_strips_and_lowercases() -> None:
    assert normalize_category("  Debug  ") == "debugging"
    assert normalize_category("PLAN_TICKET") == "ticketing"


def test_get_agent_context_new_aliases() -> None:
    assert get_agent_context("git").agent_name == "commit"
    assert get_agent_context("pr").agent_name == "pr-review"
    assert get_agent_context("db").agent_name == "debug-database"
    assert get_agent_context("react").agent_name == "frontend-developer"
    assert get_agent_context("fastapi").agent_name == "python-fastapi-expert"


def test_get_agent_context_review_recommends_pr_review_skill() -> None:
    ctx = get_agent_context("review")
    assert ctx.recommended_skill == "onex-pr-review"


def test_get_agent_context_handoff_recommends_handoff_skill() -> None:
    ctx = get_agent_context("handoff")
    assert ctx.agent_name == "handoff-guide"
    assert ctx.recommended_skill == "onex-handoff"


def test_pr_review_and_address_pr_comments_categories_disambiguated() -> None:
    """A9 residual: both configs shipped `"category": "review"` — pinned apart.

    Deliberately NOT a global category-uniqueness guard (whether categories
    must be unique across .cursor/agents/ is a review-time decision; a CI
    uniqueness gate is Phase-2 A10.7 scope).
    """
    import json
    from pathlib import Path

    agents_dir = Path(__file__).resolve().parents[1] / ".cursor" / "agents"
    pr_review = json.loads((agents_dir / "pr-review.json").read_text(encoding="utf-8"))
    address = json.loads(
        (agents_dir / "address-pr-comments.json").read_text(encoding="utf-8")
    )
    assert pr_review["category"] == "review"
    assert address["category"] == "review-response"
    assert pr_review["category"] != address["category"]

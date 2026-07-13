"""Direct unit tests for .cursor/hooks/lib/agent_scoring.py.

agent_scoring.py is the canonical scoring engine shared by on_prompt.py,
user-prompt-submit.py, and agents.py (via importlib bridge). These tests
exercise every exported symbol directly so regressions surface here rather
than being buried inside hook integration tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make lib/ importable without installing
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / ".cursor" / "hooks" / "lib")
)

from agent_scoring import (  # noqa: E402
    HARD_FLOOR,
    STOPWORDS,
    extract_keywords,
    fuzzy_threshold,
    score_agent,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_hard_floor_value() -> None:
    assert HARD_FLOOR == 0.55


def test_stopwords_is_frozenset() -> None:
    assert isinstance(STOPWORDS, frozenset)


def test_stopwords_contains_common_words() -> None:
    for word in ("the", "a", "an", "and", "is", "in", "of", "to"):
        assert word in STOPWORDS


def test_stopwords_does_not_contain_significant_words() -> None:
    for word in ("debug", "error", "test", "review", "plan"):
        assert word not in STOPWORDS


# ---------------------------------------------------------------------------
# extract_keywords
# ---------------------------------------------------------------------------


def test_extract_keywords_removes_stopwords() -> None:
    result = extract_keywords("the error is in the authentication module")
    assert "the" not in result
    assert "is" not in result
    assert "in" not in result
    assert "error" in result
    assert "authentication" in result
    assert "module" in result


def test_extract_keywords_removes_short_words() -> None:
    result = extract_keywords("do it now")
    # "do", "it", "now" — "do" and "it" are ≤2 chars; "now" is 3 chars and not in stopwords
    assert "do" not in result
    assert "it" not in result
    assert "now" in result


def test_extract_keywords_lowercases() -> None:
    result = extract_keywords("Debug the Authentication Module")
    assert "debug" in result
    assert "authentication" in result
    assert "module" in result
    assert "Debug" not in result


def test_extract_keywords_empty_string() -> None:
    assert extract_keywords("") == []


def test_extract_keywords_all_stopwords() -> None:
    assert extract_keywords("the a an and is in of to") == []


# ---------------------------------------------------------------------------
# fuzzy_threshold
# ---------------------------------------------------------------------------


def test_fuzzy_threshold_short_trigger() -> None:
    # ≤6 chars → 0.85
    assert fuzzy_threshold("debug") == 0.85
    assert fuzzy_threshold("fix") == 0.85
    assert fuzzy_threshold("review") == 0.85


def test_fuzzy_threshold_medium_trigger() -> None:
    # 7–10 chars → 0.78
    assert fuzzy_threshold("debugger") == 0.78
    assert fuzzy_threshold("refactor") == 0.78
    assert fuzzy_threshold("brainstorm") == 0.78


def test_fuzzy_threshold_long_trigger() -> None:
    # >10 chars → 0.72
    assert fuzzy_threshold("authentication") == 0.72
    assert fuzzy_threshold("performance optimization") == 0.72


def test_fuzzy_threshold_boundary_6() -> None:
    assert fuzzy_threshold("x" * 6) == 0.85


def test_fuzzy_threshold_boundary_7() -> None:
    assert fuzzy_threshold("x" * 7) == 0.78


def test_fuzzy_threshold_boundary_10() -> None:
    assert fuzzy_threshold("x" * 10) == 0.78


def test_fuzzy_threshold_boundary_11() -> None:
    assert fuzzy_threshold("x" * 11) == 0.72


# ---------------------------------------------------------------------------
# score_agent — Strategy 1: exact explicit_trigger match
# ---------------------------------------------------------------------------

_AGENT_DEBUGGING = {
    "name": "systematic-debugger",
    "activation_patterns": {
        "explicit_triggers": ["debug", "traceback", "stack trace"],
        "context_triggers": ["error", "exception"],
        "activation_keywords": ["debug", "fix", "traceback", "crash"],
    },
}

_AGENT_BRAINSTORM = {
    "name": "brainstorming-guide",
    "activation_patterns": {
        "explicit_triggers": ["brainstorm", "explore options", "ideate"],
        "context_triggers": ["ideas", "approaches"],
        "activation_keywords": ["brainstorm", "options", "ideas", "explore"],
    },
}

_AGENT_NO_PATTERNS = {
    "name": "polymorphic-agent",
    "activation_patterns": {
        "explicit_triggers": [],
        "context_triggers": [],
        "activation_keywords": [],
    },
}


def test_exact_explicit_trigger_returns_095() -> None:
    prompt = "help me debug this error"
    prompt_words = set(extract_keywords(prompt))
    score, reason = score_agent(prompt, prompt_words, _AGENT_DEBUGGING)
    assert score == pytest.approx(0.95)
    assert "debug" in reason.lower()


def test_exact_explicit_trigger_case_insensitive() -> None:
    prompt = "I need to see the TRACEBACK"
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    score, reason = score_agent(prompt_lower, prompt_words, _AGENT_DEBUGGING)
    assert score == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# score_agent — Strategy 2: exact context_trigger match
# ---------------------------------------------------------------------------


def test_context_trigger_returns_080_when_no_explicit_match() -> None:
    prompt = "there is an exception in the code"
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    score, reason = score_agent(prompt_lower, prompt_words, _AGENT_DEBUGGING)
    assert score == pytest.approx(0.80)
    assert "context trigger" in reason.lower() or "exception" in reason.lower()


def test_explicit_trigger_beats_context_trigger() -> None:
    prompt = "debug the exception"  # both "debug" (explicit) and "exception" (context)
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    score, reason = score_agent(prompt_lower, prompt_words, _AGENT_DEBUGGING)
    assert score == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# score_agent — Strategy 3: keyword overlap
# ---------------------------------------------------------------------------


def test_keyword_overlap_requires_at_least_two_matches() -> None:
    # Only one keyword match — should score 0.0
    prompt = "brainstorm the problem"
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    score, _reason = score_agent(prompt_lower, prompt_words, _AGENT_BRAINSTORM)
    # "brainstorm" is an exact explicit trigger — score is 0.95, not testing keyword path here
    # Use a different agent that has no explicit/context match
    agent = {
        "name": "test-agent",
        "activation_patterns": {
            "explicit_triggers": [],
            "context_triggers": [],
            "activation_keywords": ["alpha", "beta", "gamma", "delta"],
        },
    }
    prompt2 = "the alpha value matters"
    prompt2_lower = prompt2.lower()
    prompt2_words = set(extract_keywords(prompt2_lower))
    score2, _ = score_agent(prompt2_lower, prompt2_words, agent)
    assert score2 == 0.0  # only 1 keyword match, need ≥2


def test_keyword_overlap_two_matches_scores_above_hard_floor() -> None:
    agent = {
        "name": "test-agent",
        "activation_patterns": {
            "explicit_triggers": [],
            "context_triggers": [],
            "activation_keywords": ["alpha", "beta", "gamma", "delta"],
        },
    }
    prompt = "check the alpha and beta configuration"
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    score, reason = score_agent(prompt_lower, prompt_words, agent)
    assert score >= HARD_FLOOR
    assert "keywords" in reason.lower()


def test_keyword_overlap_scales_with_coverage() -> None:
    agent = {
        "name": "test-agent",
        "activation_patterns": {
            "explicit_triggers": [],
            "context_triggers": [],
            "activation_keywords": ["alpha", "beta", "gamma", "delta"],
        },
    }
    # 2/4 keywords
    p2 = "alpha and beta test"
    p2_lower = p2.lower()
    score_2, _ = score_agent(p2_lower, set(extract_keywords(p2_lower)), agent)

    # 4/4 keywords
    p4 = "alpha beta gamma delta test"
    p4_lower = p4.lower()
    score_4, _ = score_agent(p4_lower, set(extract_keywords(p4_lower)), agent)

    assert score_4 > score_2


# ---------------------------------------------------------------------------
# score_agent — no match
# ---------------------------------------------------------------------------


def test_no_match_returns_zero() -> None:
    prompt = "write a poem about flowers"
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    score, reason = score_agent(prompt_lower, prompt_words, _AGENT_DEBUGGING)
    assert score == 0.0
    assert reason == ""


def test_empty_activation_patterns_returns_zero() -> None:
    prompt = "debug error traceback exception crash fix"
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    score, reason = score_agent(prompt_lower, prompt_words, _AGENT_NO_PATTERNS)
    assert score == 0.0


# ---------------------------------------------------------------------------
# score_agent — best score wins across strategies
# ---------------------------------------------------------------------------


def test_score_never_exceeds_095() -> None:
    prompt = "debug traceback stack trace exception error crash fix"
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    score, _ = score_agent(prompt_lower, prompt_words, _AGENT_DEBUGGING)
    assert score <= 0.95


def test_returns_tuple_of_float_and_str() -> None:
    prompt = "debug this"
    prompt_lower = prompt.lower()
    prompt_words = set(extract_keywords(prompt_lower))
    result = score_agent(prompt_lower, prompt_words, _AGENT_DEBUGGING)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], float)
    assert isinstance(result[1], str)

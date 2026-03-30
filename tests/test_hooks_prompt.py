"""Tests for .cursor/hooks/on_prompt.py — prompt classification."""

import sys
from pathlib import Path

import pytest

# Make hook modules importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".cursor" / "hooks"))

from _common import load_agent_configs
from on_prompt import classify_prompt


@pytest.fixture
def agents():
    """Load the real agent configs from .cursor/agents/."""
    return load_agent_configs()


# ---------------------------------------------------------------------------
# Classification with real agent configs
# ---------------------------------------------------------------------------


class TestClassifyWithRealAgents:
    def test_debug_prompt(self, agents):
        name, score = classify_prompt(
            "I need to debug this error in the authentication module", agents
        )
        assert name == "debug-intelligence"
        assert score > 0

    def test_pr_review_prompt(self, agents):
        name, score = classify_prompt("Please do a pr review of the latest changes", agents)
        assert score > 0
        assert name == "pr-review"

    def test_summarize_prompt(self, agents):
        name, score = classify_prompt("Summarize this document for me", agents)
        assert name == "content-summarizer"
        assert score > 0

    def test_commit_prompt(self, agents):
        name, score = classify_prompt("Help me write a commit message", agents)
        assert name == "commit"
        assert score > 0

    def test_unmatched_prompt_falls_back(self, agents):
        name, score = classify_prompt("What is the weather today?", agents)
        assert name == "polymorphic-agent"
        assert score == 0.0

    def test_testing_prompt(self, agents):
        name, score = classify_prompt("Write unit tests for the API module", agents)
        assert name == "testing"
        assert score > 0

    def test_security_prompt(self, agents):
        name, score = classify_prompt(
            "Run a security audit on the authentication flow", agents
        )
        assert name == "security-audit"
        assert score > 0

    def test_performance_prompt(self, agents):
        name, score = classify_prompt(
            "The application is slow, need to optimize performance", agents
        )
        assert name == "performance"
        assert score > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestClassifyEdgeCases:
    def test_empty_prompt_returns_fallback(self, agents):
        name, score = classify_prompt("", agents)
        assert name == "polymorphic-agent"
        assert score == 0.0

    def test_empty_agents_returns_fallback(self):
        name, score = classify_prompt("debug this error", [])
        assert name == "polymorphic-agent"
        assert score == 0.0

    def test_none_like_prompt(self, agents):
        """Even a nonsensical string should not crash."""
        name, score = classify_prompt("   ", agents)
        assert isinstance(name, str)
        assert isinstance(score, float)

    def test_agents_with_missing_fields(self):
        """Agent configs with missing activation_patterns don't crash."""
        bad_agents = [{"name": "broken-agent"}]
        name, score = classify_prompt("debug something", bad_agents)
        assert name == "polymorphic-agent"
        assert score == 0.0

    def test_agents_with_empty_triggers(self):
        agents = [
            {
                "name": "empty-agent",
                "activation_patterns": {
                    "explicit_triggers": [],
                    "context_triggers": [],
                },
            }
        ]
        name, score = classify_prompt("anything", agents)
        assert name == "polymorphic-agent"
        assert score == 0.0

    def test_case_insensitive_matching(self):
        agents = [
            {
                "name": "test-agent",
                "activation_patterns": {
                    "explicit_triggers": ["DEBUG"],
                    "context_triggers": [],
                },
            }
        ]
        name, score = classify_prompt("I need to debug this", agents)
        assert name == "test-agent"
        assert score > 0

    def test_highest_score_wins(self):
        agents = [
            {
                "name": "agent-a",
                "activation_patterns": {
                    "explicit_triggers": ["foo", "qux"],
                    "context_triggers": [],
                },
            },
            {
                "name": "agent-b",
                "activation_patterns": {
                    "explicit_triggers": ["foo", "bar"],
                    "context_triggers": ["baz"],
                },
            },
        ]
        # agent-a: 2/4 = 0.5 (only "foo" matches)
        # agent-b: 5/5 = 1.0 (all triggers match)
        name, score = classify_prompt("foo bar baz", agents)
        assert name == "agent-b"

"""Event 1 — beforeSubmitPrompt: tests for user-prompt-submit.py.

Tests agent routing, delegation rule, and handoff nudge. All pass.
"""

from __future__ import annotations

import importlib.util as _ilu
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / ".cursor" / "hooks" / "lib"
_SCRIPTS = _ROOT / ".cursor" / "hooks" / "scripts"


def _load(name: str, path: Path) -> Any:
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Load lib/_common, overriding any cached version from .cursor/hooks/_common.py
# (other test files load the old _common; the new scripts need the lib version
# which adds write_context and updates path resolution).
_lib_common = _load("_common", _LIB / "_common.py")
_load("pattern_loader", _LIB / "pattern_loader.py")
_mod = _load("user_prompt_submit", _SCRIPTS / "user-prompt-submit.py")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
    monkeypatch.setattr(_mod, "log_event", lambda _: None)
    return sessions


@pytest.fixture
def agents() -> List[Dict[str, Any]]:
    return _lib_common.load_agent_configs()


@pytest.fixture
def conv_id() -> str:
    return "test-conv-abc123"


# ---------------------------------------------------------------------------
# classify_prompt
# ---------------------------------------------------------------------------


class TestClassifyPrompt:
    def test_debug_prompt_matches_debug_agent(self, agents: list) -> None:
        name, score, _ = _mod.classify_prompt(
            "I need to debug this error in the authentication module", agents
        )
        assert name == "debug-intelligence"
        assert score >= _mod.HARD_FLOOR

    def test_pr_review_prompt(self, agents: list) -> None:
        name, score, _ = _mod.classify_prompt(
            "Please do a pr review of the latest changes", agents
        )
        assert name == "pr-review"
        assert score >= _mod.HARD_FLOOR

    def test_unmatched_prompt_returns_fallback(self, agents: list) -> None:
        name, score, _ = _mod.classify_prompt("What is the weather today?", agents)
        assert name == "polymorphic-agent"
        assert score == 0.0

    def test_empty_prompt_returns_fallback(self, agents: list) -> None:
        name, score, _ = _mod.classify_prompt("", agents)
        assert name == "polymorphic-agent"
        assert score == 0.0

    def test_empty_agents_list_returns_fallback(self) -> None:
        name, score, _ = _mod.classify_prompt("debug this error", [])
        assert name == "polymorphic-agent"
        assert score == 0.0

    def test_case_insensitive_matching(self) -> None:
        agents = [{"name": "test-agent", "activation_patterns": {
            "explicit_triggers": ["DEBUG"], "context_triggers": [],
        }}]
        name, score, _ = _mod.classify_prompt("debug this now", agents)
        assert name == "test-agent"
        assert score >= _mod.HARD_FLOOR

    def test_highest_score_wins(self) -> None:
        agents = [
            {"name": "weak-agent", "activation_patterns": {
                "explicit_triggers": ["qux"], "context_triggers": ["bar baz"],
            }},
            {"name": "strong-agent", "activation_patterns": {
                "explicit_triggers": ["bar"], "context_triggers": [],
            }},
        ]
        # weak: context trigger → 0.80; strong: exact trigger → 0.95
        name, _, _ = _mod.classify_prompt("foo bar baz", agents)
        assert name == "strong-agent"

    def test_agent_missing_activation_patterns_does_not_crash(self) -> None:
        name, score, _ = _mod.classify_prompt("debug this", [{"name": "broken"}])
        assert name == "polymorphic-agent"
        assert score == 0.0


# ---------------------------------------------------------------------------
# _is_complex_unstructured
# ---------------------------------------------------------------------------


class TestIsComplexUnstructured:
    def test_short_prompt_not_complex(self) -> None:
        assert _mod._is_complex_unstructured("fix bug") is False

    def test_49_chars_not_complex(self) -> None:
        assert _mod._is_complex_unstructured("x" * 49) is False

    def test_50_chars_is_complex_boundary(self) -> None:
        # len < 50 exits early; exactly 50 is eligible
        assert _mod._is_complex_unstructured("x" * 50) is True

    def test_long_unstructured_is_complex(self) -> None:
        assert _mod._is_complex_unstructured(
            "Please refactor the entire authentication module and add comprehensive unit tests"
        ) is True

    def test_task_field_marks_as_structured(self) -> None:
        assert _mod._is_complex_unstructured(
            "Task: refactor auth\nScope: src/auth/\nDone when: all tests pass"
        ) is False

    def test_scope_field_marks_as_structured(self) -> None:
        assert _mod._is_complex_unstructured("a" * 60 + "\nScope: src/auth/") is False

    def test_done_when_marks_as_structured(self) -> None:
        assert _mod._is_complex_unstructured("a" * 60 + "\nDone when: tests green") is False

    def test_constraints_marks_as_structured(self) -> None:
        assert _mod._is_complex_unstructured("a" * 60 + "\nConstraints: no touching tests") is False

    def test_workflow_marks_as_structured(self) -> None:
        assert _mod._is_complex_unstructured("a" * 60 + "\nWorkflow: /ticket-pipeline") is False

    def test_skill_invocation_not_complex(self) -> None:
        assert _mod._is_complex_unstructured(
            "/systematic-debugging fix login flow errors in the auth module"
        ) is False

    def test_structure_check_case_insensitive(self) -> None:
        assert _mod._is_complex_unstructured("a" * 60 + "\nTASK: do something") is False


# ---------------------------------------------------------------------------
# should_nudge / mark_nudge_fired
# ---------------------------------------------------------------------------


class TestNudgeState:
    def test_fresh_session_should_nudge(self, fake_sessions: Path, conv_id: str) -> None:
        assert _mod.should_nudge(conv_id) is True

    def test_after_mark_fired_no_nudge(self, fake_sessions: Path, conv_id: str) -> None:
        _mod.mark_nudge_fired(conv_id)
        assert _mod.should_nudge(conv_id) is False

    def test_empty_conv_id_no_nudge(self, fake_sessions: Path) -> None:
        assert _mod.should_nudge("") is False

    def test_sessions_are_independent(self, fake_sessions: Path) -> None:
        _mod.mark_nudge_fired("session-A")
        assert _mod.should_nudge("session-A") is False
        assert _mod.should_nudge("session-B") is True

    def test_mark_empty_id_does_not_crash(self, fake_sessions: Path) -> None:
        _mod.mark_nudge_fired("")


# ---------------------------------------------------------------------------
# reset_turn_state
# ---------------------------------------------------------------------------


class TestResetTurnState:
    def test_creates_write_count_zero(self, fake_sessions: Path, conv_id: str) -> None:
        _mod.reset_turn_state(conv_id)
        assert (fake_sessions / conv_id / "write_count").read_text() == "0"

    def test_creates_read_count_zero(self, fake_sessions: Path, conv_id: str) -> None:
        _mod.reset_turn_state(conv_id)
        assert (fake_sessions / conv_id / "read_count").read_text() == "0"

    def test_overwrites_existing_counts(self, fake_sessions: Path, conv_id: str) -> None:
        d = fake_sessions / conv_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "write_count").write_text("7")
        (d / "read_count").write_text("3")
        _mod.reset_turn_state(conv_id)
        assert (d / "write_count").read_text() == "0"
        assert (d / "read_count").read_text() == "0"

    def test_removes_delegated_flag(self, fake_sessions: Path, conv_id: str) -> None:
        d = fake_sessions / conv_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "delegated").touch()
        _mod.reset_turn_state(conv_id)
        assert not (d / "delegated").exists()

    def test_empty_conv_id_does_not_crash(self, fake_sessions: Path) -> None:
        _mod.reset_turn_state("")


# ---------------------------------------------------------------------------
# build_context
# ---------------------------------------------------------------------------


class TestBuildContext:
    def test_routing_section_always_present(self, fake_sessions: Path, conv_id: str) -> None:
        out = _mod.build_context("debug-intelligence", 0.95, "Exact trigger", [], "hi", conv_id)
        assert "## OmniCursor Agent Routing" in out

    def test_agent_name_in_output(self, fake_sessions: Path, conv_id: str) -> None:
        out = _mod.build_context("my-agent", 0.80, "reason", [], "prompt", conv_id)
        assert "`my-agent`" in out

    def test_confidence_score_in_output(self, fake_sessions: Path, conv_id: str) -> None:
        out = _mod.build_context("agent", 0.92, "reason", [], "prompt", conv_id)
        assert "0.92" in out

    def test_delegation_section_always_present(self, fake_sessions: Path, conv_id: str) -> None:
        out = _mod.build_context("agent", 0.5, "reason", [], "prompt", conv_id)
        assert "## Delegation Rule" in out

    def test_delegation_threshold_in_text(self, fake_sessions: Path, conv_id: str) -> None:
        out = _mod.build_context("agent", 0.5, "reason", [], "prompt", conv_id)
        assert str(_mod.DELEGATION_THRESHOLD) in out

    def test_sections_separated_by_horizontal_rule(self, fake_sessions: Path, conv_id: str) -> None:
        out = _mod.build_context("agent", 0.5, "reason", [], "prompt", conv_id)
        assert "---" in out

    def test_patterns_listed(self, fake_sessions: Path, conv_id: str) -> None:
        patterns = [
            {"pattern_id": "p1", "description": "Use binary search"},
            {"pattern_id": "p2", "description": "Prefer composition"},
        ]
        out = _mod.build_context("agent", 0.8, "reason", patterns, "prompt", conv_id)
        assert "p1" in out and "Use binary search" in out
        assert "p2" in out and "Prefer composition" in out

    def test_max_5_patterns_injected(self, fake_sessions: Path, conv_id: str) -> None:
        patterns = [{"pattern_id": f"p{i}", "description": f"d{i}"} for i in range(10)]
        out = _mod.build_context("agent", 0.8, "reason", patterns, "prompt", conv_id)
        assert "p5" not in out and "p9" not in out

    def test_nudge_fires_for_first_complex_unstructured(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        long = "Please refactor the entire authentication module and add comprehensive unit tests"
        out = _mod.build_context("agent", 0.5, "r", [], long, conv_id)
        assert "## Handoff Tip" in out

    def test_nudge_absent_for_short_prompt(self, fake_sessions: Path, conv_id: str) -> None:
        out = _mod.build_context("agent", 0.5, "r", [], "fix bug", conv_id)
        assert "Handoff Tip" not in out

    def test_nudge_absent_for_structured_prompt(self, fake_sessions: Path, conv_id: str) -> None:
        structured = "Task: refactor auth\nScope: src/auth/\nDone when: tests pass"
        out = _mod.build_context("agent", 0.5, "r", [], structured, conv_id)
        assert "Handoff Tip" not in out

    def test_nudge_absent_for_skill_invocation(self, fake_sessions: Path, conv_id: str) -> None:
        skill = "/systematic-debugging fix the login flow errors in the auth module please"
        out = _mod.build_context("agent", 0.5, "r", [], skill, conv_id)
        assert "Handoff Tip" not in out

    def test_nudge_fires_only_once_per_session(self, fake_sessions: Path, conv_id: str) -> None:
        long = "Please refactor the entire authentication module and add comprehensive tests"
        out1 = _mod.build_context("agent", 0.5, "r", [], long, conv_id)
        out2 = _mod.build_context("agent", 0.5, "r", [], long, conv_id)
        assert "Handoff Tip" in out1
        assert "Handoff Tip" not in out2

    def test_nudge_absent_when_conv_id_empty(self, fake_sessions: Path) -> None:
        long = "Please refactor the entire authentication module and add comprehensive tests"
        out = _mod.build_context("agent", 0.5, "r", [], long, "")
        assert "Handoff Tip" not in out


# ---------------------------------------------------------------------------
# Full stdin → stdout pipeline
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_valid_stdin_produces_system_message(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "prompt": "I need to debug this error in the authentication module",
            "conversation_id": "pipe-001",
        }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        result = json.loads(out.getvalue().strip())
        assert "systemMessage" in result
        assert isinstance(result["systemMessage"], str)
        assert len(result["systemMessage"]) > 0

    def test_empty_stdin_emits_valid_json(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        assert "systemMessage" in json.loads(out.getvalue().strip())

    def test_malformed_stdin_emits_valid_json(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("not json {{"))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        assert "systemMessage" in json.loads(out.getvalue().strip())

    def test_output_contains_routing_section(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {"prompt": "debug authentication error", "conversation_id": "pipe-002"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        msg = json.loads(out.getvalue().strip())["systemMessage"]
        assert "## OmniCursor Agent Routing" in msg

    def test_output_contains_delegation_rule(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {"prompt": "help me out", "conversation_id": "pipe-003"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        msg = json.loads(out.getvalue().strip())["systemMessage"]
        assert "## Delegation Rule" in msg

    def test_fallback_agent_for_unmatched_prompt(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {"prompt": "what is the weather today?", "conversation_id": "pipe-004"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        msg = json.loads(out.getvalue().strip())["systemMessage"]
        assert "polymorphic-agent" in msg


# ---------------------------------------------------------------------------
# Session identity
# ---------------------------------------------------------------------------


class TestSessionIdentity:
    def test_init_session_creates_flag(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._init_session(conv_id)
        assert (fake_sessions / conv_id / "session_initialized").exists()

    def test_init_session_writes_current_json(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._init_session(conv_id)
        current = fake_sessions / "current.json"
        assert current.exists()
        data = json.loads(current.read_text())
        assert data["conversation_id"] == conv_id
        assert "started_at" in data

    def test_init_session_idempotent(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._init_session(conv_id)
        mtime_before = (fake_sessions / conv_id / "session_initialized").stat().st_mtime
        _mod._init_session(conv_id)
        assert (fake_sessions / conv_id / "session_initialized").stat().st_mtime == mtime_before

    def test_second_init_does_not_overwrite_current_json(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._init_session(conv_id)
        first_content = (fake_sessions / "current.json").read_text()
        _mod._init_session(conv_id)
        assert (fake_sessions / "current.json").read_text() == first_content

    def test_different_conv_ids_each_get_flag(
        self, fake_sessions: Path
    ) -> None:
        _mod._init_session("session-A")
        _mod._init_session("session-B")
        assert (fake_sessions / "session-A" / "session_initialized").exists()
        assert (fake_sessions / "session-B" / "session_initialized").exists()

    def test_empty_conv_id_does_not_crash(self, fake_sessions: Path) -> None:
        _mod._init_session("")

    def test_main_triggers_session_init(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {"prompt": "fix bug", "conversation_id": "init-test-001"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        assert (fake_sessions / "init-test-001" / "session_initialized").exists()


# ---------------------------------------------------------------------------
# Correlation ID
# ---------------------------------------------------------------------------


class TestCorrelationId:
    def test_generates_12_char_hex(self) -> None:
        cid = _mod._generate_correlation_id()
        assert len(cid) == 12
        assert all(c in "0123456789abcdef" for c in cid)

    def test_each_call_is_unique(self) -> None:
        ids = {_mod._generate_correlation_id() for _ in range(100)}
        assert len(ids) == 100

    def test_correlation_id_appears_in_header(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "prompt", conv_id, correlation_id="abc123def456"
        )
        assert "abc123def456" in out

    def test_no_correlation_id_omits_comment_line(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "prompt", conv_id, correlation_id=""
        )
        assert "OmniCursor: correlation=" not in out

    def test_main_emits_correlation_id_in_log(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        payload = {"prompt": "fix bug", "conversation_id": "corr-001"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        assert len(events) == 1
        assert "correlation_id" in events[0]
        assert len(events[0]["correlation_id"]) == 12


# ---------------------------------------------------------------------------
# Pattern relevance filtering
# ---------------------------------------------------------------------------


class TestPatternRelevance:
    def test_domain_match_scores_1_0(self) -> None:
        p = {"domain": "debug_intelligence", "description": "use breakpoints"}
        score = _mod._score_pattern_relevance(p, "debug_intelligence", set())
        assert score == 1.0

    def test_general_domain_base_score_0_6(self) -> None:
        p = {"domain": "general", "description": "add unit tests"}
        score = _mod._score_pattern_relevance(p, "debug_intelligence", set())
        assert score == pytest.approx(0.6)

    def test_unrelated_domain_base_score_0_3(self) -> None:
        p = {"domain": "frontend", "description": "use react components"}
        score = _mod._score_pattern_relevance(p, "debug_intelligence", set())
        assert score == pytest.approx(0.3)

    def test_keyword_overlap_boosts_score(self) -> None:
        p = {"domain": "general", "description": "check authentication traces"}
        score_no_overlap = _mod._score_pattern_relevance(p, "debug_intelligence", set())
        score_with_overlap = _mod._score_pattern_relevance(
            p, "debug_intelligence", {"authentication", "traces", "check"}
        )
        assert score_with_overlap > score_no_overlap

    def test_score_capped_at_1_0(self) -> None:
        # Domain match (1.0) + overlap boost should not exceed 1.0
        p = {"domain": "debug_intelligence", "description": "fix error trace"}
        score = _mod._score_pattern_relevance(
            p, "debug_intelligence", {"fix", "error", "trace"}
        )
        assert score <= 1.0

    def test_filter_removes_low_relevance_patterns(self) -> None:
        patterns = [
            {"domain": "frontend", "description": "use react components"},
            {"domain": "debug_intelligence", "description": "trace the error"},
        ]
        result = _mod._filter_patterns_by_relevance(
            patterns, "debug_intelligence", set()
        )
        descriptions = [p["description"] for p in result]
        assert "trace the error" in descriptions
        assert "use react components" not in descriptions

    def test_filter_ranks_domain_match_first(self) -> None:
        patterns = [
            {"domain": "general", "description": "add tests", "pattern_id": "g1"},
            {"domain": "debug_intelligence", "description": "trace error", "pattern_id": "d1"},
        ]
        result = _mod._filter_patterns_by_relevance(
            patterns, "debug_intelligence", set()
        )
        assert result[0]["pattern_id"] == "d1"

    def test_filter_caps_at_max_patterns(self) -> None:
        patterns = [
            {"domain": "debug_intelligence", "description": f"pattern {i}"}
            for i in range(20)
        ]
        result = _mod._filter_patterns_by_relevance(
            patterns, "debug_intelligence", set()
        )
        assert len(result) <= _mod.MAX_PATTERNS

    def test_filter_empty_input_returns_empty(self) -> None:
        result = _mod._filter_patterns_by_relevance([], "debug_intelligence", set())
        assert result == []

    def test_general_pattern_below_threshold_excluded(self) -> None:
        # "general" domain with no keyword overlap scores 0.6, below 0.7 threshold
        patterns = [{"domain": "general", "description": "something unrelated"}]
        result = _mod._filter_patterns_by_relevance(patterns, "debug_intelligence", set())
        assert result == []


# ---------------------------------------------------------------------------
# Complexity estimator
# ---------------------------------------------------------------------------


class TestComplexityEstimator:
    def test_short_prompt_not_complex(self) -> None:
        assert _mod._estimate_complexity("fix bug") is False

    def test_under_80_chars_not_complex(self) -> None:
        assert _mod._estimate_complexity("x" * 79) is False

    def test_complex_verb_plus_multi_step_marker_triggers(self) -> None:
        prompt = (
            "Please refactor the authentication module and then integrate it "
            "with the new payment API service layer so everything is consistent"
        )
        assert _mod._estimate_complexity(prompt) is True

    def test_two_complex_verbs_triggers(self) -> None:
        prompt = (
            "Migrate the database schema and implement the new user registration "
            "flow with all required validation and error handling throughout"
        )
        assert _mod._estimate_complexity(prompt) is True

    def test_long_prompt_no_complex_verbs_not_complex(self) -> None:
        # 100 chars, no verbs from _COMPLEX_VERBS, no multi-step marker
        assert _mod._estimate_complexity("x" * 100) is False

    def test_single_verb_no_multi_step_not_complex(self) -> None:
        prompt = (
            "Please refactor this function so that the logic is cleaner and "
            "easier to read for other developers who come after us on the team"
        )
        assert _mod._estimate_complexity(prompt) is False

    def test_additionally_counts_as_multi_step_marker(self) -> None:
        prompt = (
            "Build the new authentication service and additionally integrate "
            "it with the existing session management code in the repository"
        )
        assert _mod._estimate_complexity(prompt) is True

    def test_exactly_80_chars_is_eligible(self) -> None:
        # len < 80 exits False; exactly 80 is eligible for further checks
        base = "x" * 80
        assert _mod._estimate_complexity(base) is False  # no verbs, so still False
        # But the length gate passed — confirm it's not failing on length alone
        with_verbs = "Please refactor and migrate " + "x" * 54  # 80 chars total
        # 'refactor' and 'migrate' are both complex verbs → True
        assert _mod._estimate_complexity(with_verbs) is True


# ---------------------------------------------------------------------------
# Agent persona depth
# ---------------------------------------------------------------------------


class TestAgentPersona:
    def test_agent_description_in_output(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        cfg = {
            "description": "Expert debugging and root cause analysis",
            "instructions": [],
            "recommended_skill": None,
        }
        out = _mod.build_context(
            "debug-intelligence", 0.9, "r", [], "prompt", conv_id, agent_config=cfg
        )
        assert "Expert debugging and root cause analysis" in out

    def test_agent_instructions_in_output(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        cfg = {
            "description": "",
            "instructions": [
                "Reproduce before fixing",
                "Test the narrowest repro first",
            ],
            "recommended_skill": None,
        }
        out = _mod.build_context(
            "debug-intelligence", 0.9, "r", [], "prompt", conv_id, agent_config=cfg
        )
        assert "Reproduce before fixing" in out
        assert "Test the narrowest repro first" in out

    def test_recommended_skill_in_output(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        cfg = {
            "description": "",
            "instructions": [],
            "recommended_skill": "systematic-debugging",
        }
        out = _mod.build_context(
            "debug-intelligence", 0.9, "r", [], "prompt", conv_id, agent_config=cfg
        )
        assert "systematic-debugging" in out

    def test_no_skill_skips_skill_line(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        cfg = {"description": "desc", "instructions": [], "recommended_skill": None}
        out = _mod.build_context(
            "agent", 0.8, "r", [], "prompt", conv_id, agent_config=cfg
        )
        assert "Recommended skill" not in out

    def test_no_agent_config_does_not_crash(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context("debug-intelligence", 0.9, "r", [], "prompt", conv_id)
        assert "## OmniCursor Agent Routing" in out

    def test_main_injects_agent_description_from_real_configs(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "prompt": "I need to debug this error in the authentication module",
            "conversation_id": "persona-001",
        }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        msg = json.loads(out.getvalue().strip())["systemMessage"]
        # debug-intelligence agent JSON has a "description" field
        assert "debug" in msg.lower() or "root cause" in msg.lower()


# ---------------------------------------------------------------------------
# HTML comment header
# ---------------------------------------------------------------------------


class TestHtmlCommentHeader:
    def test_agent_comment_present(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context("my-agent", 0.8, "r", [], "hi", conv_id)
        assert "<!-- OmniCursor: agent=my-agent" in out

    def test_confidence_in_comment(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context("my-agent", 0.80, "r", [], "hi", conv_id)
        assert "confidence=0.80" in out

    def test_patterns_count_in_comment(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        patterns = [{"pattern_id": "p1", "description": "use tests"}]
        out = _mod.build_context("my-agent", 0.8, "r", patterns, "hi", conv_id)
        assert "<!-- OmniCursor: patterns=1 injected" in out

    def test_zero_patterns_count_in_comment(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context("my-agent", 0.8, "r", [], "hi", conv_id)
        assert "<!-- OmniCursor: patterns=0 injected" in out

    def test_delegation_advisory_label(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "hi", conv_id, delegation_required=False
        )
        assert "delegation=advisory" in out

    def test_delegation_required_label(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "hi", conv_id, delegation_required=True
        )
        assert "delegation=required" in out

    def test_correlation_comment_present_when_given(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "hi", conv_id, correlation_id="deadbeef1234"
        )
        assert "<!-- OmniCursor: correlation=deadbeef1234 -->" in out

    def test_header_comes_before_body(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context("agent", 0.5, "r", [], "hi", conv_id)
        header_pos = out.find("<!-- OmniCursor:")
        routing_pos = out.find("## OmniCursor Agent Routing")
        assert header_pos < routing_pos


# ---------------------------------------------------------------------------
# Delegation required vs advisory
# ---------------------------------------------------------------------------


class TestDelegationRequired:
    def test_required_uses_must_keyword(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "prompt", conv_id, delegation_required=True
        )
        assert "MUST" in out

    def test_advisory_does_not_use_must(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "prompt", conv_id, delegation_required=False
        )
        assert "MUST" not in out

    def test_advisory_references_threshold(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "prompt", conv_id, delegation_required=False
        )
        assert str(_mod.DELEGATION_THRESHOLD) in out

    def test_required_says_first_action(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context(
            "agent", 0.5, "r", [], "prompt", conv_id, delegation_required=True
        )
        assert "first action" in out

    def test_complex_prompt_in_main_sets_delegation_required(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        complex_prompt = (
            "Please refactor the authentication module and then integrate it "
            "with the new payment service API so the flow is consistent end to end"
        )
        payload = {"prompt": complex_prompt, "conversation_id": "deleg-001"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        assert events[0]["delegation_required"] is True

    def test_simple_prompt_in_main_sets_delegation_advisory(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        payload = {"prompt": "fix the typo", "conversation_id": "deleg-002"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        assert events[0]["delegation_required"] is False


# ---------------------------------------------------------------------------
# Typed event schema
# ---------------------------------------------------------------------------


class TestTypedEventSchema:
    def _run_main(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_sessions: Path,
        prompt: str = "fix bug",
        conv_id: str = "schema-001",
    ) -> Dict:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        payload = {"prompt": prompt, "conversation_id": conv_id, "generation_id": "gen-x"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        return events[0]

    def test_event_type_is_prompt_classified(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions)
        assert e["event"] == "prompt_classified"

    def test_event_has_conversation_id(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions)
        assert e["conversation_id"] == "schema-001"

    def test_event_has_correlation_id(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions)
        assert "correlation_id" in e and len(e["correlation_id"]) == 12

    def test_event_has_matched_agent(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions)
        assert "matched_agent" in e

    def test_event_has_score(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions)
        assert "score" in e and isinstance(e["score"], float)

    def test_event_has_patterns_injected_count(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions)
        assert "patterns_injected" in e and isinstance(e["patterns_injected"], int)

    def test_event_has_delegation_required_bool(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions)
        assert "delegation_required" in e and isinstance(e["delegation_required"], bool)

    def test_event_has_prompt_snippet(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions, prompt="fix the typo in login")
        assert "prompt_snippet" in e
        assert "fix the typo" in e["prompt_snippet"]

    def test_event_has_hook_duration_ms(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main(monkeypatch, fake_sessions)
        assert "hook_duration_ms" in e and isinstance(e["hook_duration_ms"], int)

    def test_prompt_snippet_truncated_at_100(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        long_prompt = "x" * 200
        e = self._run_main(monkeypatch, fake_sessions, prompt=long_prompt)
        assert len(e["prompt_snippet"]) <= 100


# ---------------------------------------------------------------------------
# Session correlation update (current.json threading for Events 2–4)
# ---------------------------------------------------------------------------


class TestSessionCorrelationUpdate:
    def test_writes_correlation_to_current_json(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._init_session(conv_id)
        _mod._update_session_correlation(conv_id, "abc123def456")
        data = json.loads((fake_sessions / "current.json").read_text())
        assert data["latest_correlation_id"] == "abc123def456"

    def test_creates_current_json_if_missing(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._update_session_correlation(conv_id, "newcorrid0001")
        current = fake_sessions / "current.json"
        assert current.exists()
        assert json.loads(current.read_text())["latest_correlation_id"] == "newcorrid0001"

    def test_overwrites_previous_correlation(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._update_session_correlation(conv_id, "first0000000a")
        _mod._update_session_correlation(conv_id, "second000000")
        data = json.loads((fake_sessions / "current.json").read_text())
        assert data["latest_correlation_id"] == "second000000"

    def test_preserves_started_at_from_init_session(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._init_session(conv_id)
        started_at = json.loads((fake_sessions / "current.json").read_text())["started_at"]
        _mod._update_session_correlation(conv_id, "newcorr00001a")
        data = json.loads((fake_sessions / "current.json").read_text())
        assert data["started_at"] == started_at

    def test_main_writes_correlation_to_current_json(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {"prompt": "fix bug", "conversation_id": "corr-write-001"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        data = json.loads((fake_sessions / "current.json").read_text())
        assert "latest_correlation_id" in data
        assert len(data["latest_correlation_id"]) == 12

    def test_each_prompt_updates_correlation(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for i in range(3):
            payload = {"prompt": f"prompt {i}", "conversation_id": "multi-prompt"}
            monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
            monkeypatch.setattr(sys, "stdout", io.StringIO())
            _mod.main()
        data = json.loads((fake_sessions / "current.json").read_text())
        # After 3 prompts the field exists and is a fresh 12-char hex ID
        assert len(data["latest_correlation_id"]) == 12


# ---------------------------------------------------------------------------
# Recap injection
# ---------------------------------------------------------------------------


class TestRecapInjection:
    def test_recap_injected_when_file_exists(
        self, tmp_path: Path, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recap_path = tmp_path / "last-recap.md"
        recap_path.write_text("## Session Recap (auto)\n**Outcome:** success")
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        payload = {"prompt": "hello", "conversation_id": "recap-test-001"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        system_msg = json.loads(out.getvalue().strip()).get("systemMessage", "")
        assert "Session Recap" in system_msg

    def test_recap_file_deleted_after_inject(
        self, tmp_path: Path, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recap_path = tmp_path / "last-recap.md"
        recap_path.write_text("## Session Recap (auto)\n**Outcome:** success")
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        payload = {"prompt": "hello", "conversation_id": "recap-test-002"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        assert not recap_path.exists()

    def test_no_recap_when_file_absent(
        self, tmp_path: Path, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recap_path = tmp_path / "last-recap.md"
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        payload = {"prompt": "hello", "conversation_id": "recap-test-003"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        system_msg = json.loads(out.getvalue().strip()).get("systemMessage", "")
        assert "Session Recap" not in system_msg


# ---------------------------------------------------------------------------
# Seed pattern fallback
# ---------------------------------------------------------------------------


class TestSeedPatternFallback:
    """When LEARNED_PATTERNS_FILE is absent, the hook loads from SEED_PATTERNS_FILE."""

    def test_seed_file_loaded_when_user_file_missing(
        self, tmp_path: Path, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Seed file warms the cache when ~/.omnicursor/learned_patterns.json absent."""
        seed = tmp_path / "seed.json"
        seed.write_text(json.dumps({"patterns": [
            {"pattern_id": "s1", "domain": "general", "description": "use git bisect", "pattern": "bisect git", "weight": 0.75, "success_count": 1, "last_seen": 0},
        ]}))
        absent = tmp_path / "missing.json"
        # Point LEARNED_PATTERNS_FILE at non-existent path, SEED at seed file.
        monkeypatch.setattr(_mod, "LEARNED_PATTERNS_FILE", absent)
        monkeypatch.setattr(_mod, "SEED_PATTERNS_FILE", seed)
        # Reset cache state so warm_from_json is called.
        from omnicursor.pattern_cache import PatternCache
        fresh_cache = PatternCache()
        monkeypatch.setattr(_mod, "get_pattern_cache", lambda: fresh_cache)
        payload = {"prompt": "use git bisect to find regression", "conversation_id": "seed-test-001"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        assert fresh_cache.is_warm()

    def test_user_file_takes_precedence_over_seed(
        self, tmp_path: Path, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When both files exist, LEARNED_PATTERNS_FILE is used, not seed."""
        user_file = tmp_path / "learned.json"
        user_file.write_text(json.dumps({"patterns": [
            {"pattern_id": "u1", "domain": "general", "description": "user pattern", "pattern": "user pattern", "weight": 0.8, "success_count": 5, "last_seen": 0},
        ]}))
        seed = tmp_path / "seed.json"
        seed.write_text(json.dumps({"patterns": [
            {"pattern_id": "s1", "domain": "general", "description": "seed pattern", "pattern": "seed pattern", "weight": 0.75, "success_count": 1, "last_seen": 0},
        ]}))
        monkeypatch.setattr(_mod, "LEARNED_PATTERNS_FILE", user_file)
        monkeypatch.setattr(_mod, "SEED_PATTERNS_FILE", seed)
        from omnicursor.pattern_cache import PatternCache
        fresh_cache = PatternCache()
        monkeypatch.setattr(_mod, "get_pattern_cache", lambda: fresh_cache)
        payload = {"prompt": "hello", "conversation_id": "seed-test-002"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        patterns = fresh_cache.get("general")
        descriptions = [p.get("description") for p in patterns]
        assert "user pattern" in descriptions
        assert "seed pattern" not in descriptions

    def test_seed_file_is_valid_json(self) -> None:
        """The committed seed file parses cleanly and has expected structure."""
        import json as _json
        seed_path = _ROOT / ".cursor" / "hooks" / "data" / "seed_patterns.json"
        assert seed_path.is_file(), "seed_patterns.json must exist in repo"
        data = _json.loads(seed_path.read_text(encoding="utf-8"))
        assert "patterns" in data
        assert isinstance(data["patterns"], list)
        assert len(data["patterns"]) >= 3

    def test_seed_patterns_have_required_fields(self) -> None:
        import json as _json
        seed_path = _ROOT / ".cursor" / "hooks" / "data" / "seed_patterns.json"
        data = _json.loads(seed_path.read_text(encoding="utf-8"))
        for p in data["patterns"]:
            assert "domain" in p, f"Missing 'domain' in seed pattern: {p}"
            assert "description" in p, f"Missing 'description' in seed pattern: {p}"
            assert "weight" in p, f"Missing 'weight' in seed pattern: {p}"


# ---------------------------------------------------------------------------
# Prior session context (session summary feedback loop)
# ---------------------------------------------------------------------------


class TestPriorSessionContext:
    """_load_prior_session_summary and build_context prior_summary injection."""

    def _make_summary(self, tmp_path: Path, conv_id: str, **kwargs: Any) -> Path:
        data = {
            "conversation_id": conv_id,
            "session_outcome": "success",
            "session_outcome_reason": "Completed planned work",
            "files_edited": 4,
            "languages": ["python", "typescript"],
            "prompts_classified": 6,
            "last_prompt_at": "2026-04-28T14:30:00+00:00",
            **kwargs,
        }
        path = tmp_path / f"{conv_id}.json"
        path.write_text(json.dumps(data))
        return path

    # _load_prior_session_summary ---

    def test_returns_none_when_no_sessions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "SESSIONS_DIR", tmp_path)
        result = _mod._load_prior_session_summary("new-conv")
        assert result is None

    def test_returns_summary_for_existing_session(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "SESSIONS_DIR", tmp_path)
        self._make_summary(tmp_path, "old-conv-001")
        result = _mod._load_prior_session_summary("new-conv")
        assert result is not None
        assert result["conversation_id"] == "old-conv-001"

    def test_excludes_current_conversation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "SESSIONS_DIR", tmp_path)
        self._make_summary(tmp_path, "same-conv")
        result = _mod._load_prior_session_summary("same-conv")
        assert result is None

    def test_excludes_current_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "SESSIONS_DIR", tmp_path)
        (tmp_path / "current.json").write_text(json.dumps({"conversation_id": "active"}))
        result = _mod._load_prior_session_summary("new-conv")
        assert result is None

    def test_returns_most_recent_when_multiple(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "SESSIONS_DIR", tmp_path)
        self._make_summary(tmp_path, "old-conv")
        import time as _time
        _time.sleep(0.01)
        self._make_summary(tmp_path, "new-conv-prior")
        result = _mod._load_prior_session_summary("current-conv")
        assert result is not None
        assert result["conversation_id"] == "new-conv-prior"

    def test_returns_none_on_malformed_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_mod, "SESSIONS_DIR", tmp_path)
        (tmp_path / "bad-conv.json").write_text("not json {{")
        result = _mod._load_prior_session_summary("new-conv")
        assert result is None

    # build_context with prior_summary ---

    def test_prior_section_absent_when_none(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context("agent", 0.8, "r", [], "prompt", conv_id, prior_summary=None)
        assert "Prior Session Context" not in out

    def test_prior_section_present_when_given(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        summary = {"session_outcome": "success", "files_edited": 3, "languages": ["python"], "prompts_classified": 5}
        out = _mod.build_context("agent", 0.8, "r", [], "prompt", conv_id, prior_summary=summary)
        assert "## Prior Session Context" in out

    def test_prior_section_shows_outcome(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        summary = {"session_outcome": "success", "files_edited": 2, "languages": [], "prompts_classified": 3}
        out = _mod.build_context("agent", 0.8, "r", [], "prompt", conv_id, prior_summary=summary)
        assert "success" in out

    def test_prior_section_shows_files_edited(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        summary = {"session_outcome": "success", "files_edited": 7, "languages": [], "prompts_classified": 4}
        out = _mod.build_context("agent", 0.8, "r", [], "prompt", conv_id, prior_summary=summary)
        assert "7" in out

    def test_prior_section_shows_languages(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        summary = {"session_outcome": "success", "files_edited": 1, "languages": ["python", "typescript"], "prompts_classified": 2}
        out = _mod.build_context("agent", 0.8, "r", [], "prompt", conv_id, prior_summary=summary)
        assert "python" in out
        assert "typescript" in out

    def test_prior_section_header_marker(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        summary = {"session_outcome": "success", "files_edited": 1, "languages": [], "prompts_classified": 1}
        out = _mod.build_context("agent", 0.8, "r", [], "prompt", conv_id, prior_summary=summary)
        assert "<!-- OmniCursor: prior_session=injected -->" in out

    def test_no_header_marker_when_no_prior_summary(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        out = _mod.build_context("agent", 0.8, "r", [], "prompt", conv_id, prior_summary=None)
        assert "prior_session=injected" not in out

    # main() integration ---

    def test_prior_summary_injected_on_first_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
        monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        # Write a prior session summary
        prior = {"conversation_id": "prior-conv", "session_outcome": "success",
                 "files_edited": 2, "languages": ["python"], "prompts_classified": 3}
        (sessions / "prior-conv.json").write_text(json.dumps(prior))
        payload = {"prompt": "start new work", "conversation_id": "first-new-conv"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        msg = json.loads(out.getvalue().strip())["systemMessage"]
        assert "Prior Session Context" in msg

    def test_prior_summary_not_injected_on_subsequent_prompts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
        monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        prior = {"conversation_id": "prior-conv2", "session_outcome": "success",
                 "files_edited": 1, "languages": [], "prompts_classified": 2}
        (sessions / "prior-conv2.json").write_text(json.dumps(prior))
        conv = "repeat-conv-001"
        for i in range(2):
            payload = {"prompt": f"prompt {i}", "conversation_id": conv}
            monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
            out = io.StringIO()
            monkeypatch.setattr(sys, "stdout", out)
            _mod.main()
            if i == 1:
                msg = json.loads(out.getvalue().strip())["systemMessage"]
                assert "Prior Session Context" not in msg


# ---------------------------------------------------------------------------
# injected_pattern_ids in prompt_classified log and send_event payload
# ---------------------------------------------------------------------------


class TestInjectedPatternIds:
    def _run_main_capture_log(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_sessions: Path,
        prompt: str = "fix bug",
        conv_id: str = "ids-001",
    ) -> Dict:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        payload = {"prompt": prompt, "conversation_id": conv_id}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        return events[0]

    def test_event_has_injected_pattern_ids_list(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main_capture_log(monkeypatch, fake_sessions)
        assert "injected_pattern_ids" in e
        assert isinstance(e["injected_pattern_ids"], list)

    def test_injected_pattern_ids_contains_real_ids(
        self, tmp_path: Path, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pattern in debug_intelligence domain — exact domain match → score 1.0 → always injected.
        learned = tmp_path / "learned.json"
        learned.write_text(json.dumps({"patterns": [
            {
                "pattern_id": "auto-abc123def456",
                "domain": "debug_intelligence",
                "description": "use breakpoints to isolate failures",
                "pattern": "breakpoints debug error",
                "weight": 0.8,
                "success_count": 3,
                "injection_count": 0,
                "utilization_successes": 0,
                "last_seen": 0,
            },
        ]}))
        monkeypatch.setattr(_mod, "LEARNED_PATTERNS_FILE", learned)
        from omnicursor.pattern_cache import PatternCache
        fresh_cache = PatternCache()
        monkeypatch.setattr(_mod, "get_pattern_cache", lambda: fresh_cache)
        # Prompt explicitly triggers debug-intelligence → domain=debug_intelligence → exact match.
        e = self._run_main_capture_log(
            monkeypatch, fake_sessions,
            prompt="I need to debug this error in the authentication module",
            conv_id="ids-002",
        )
        assert "auto-abc123def456" in e["injected_pattern_ids"]

    def test_pattern_without_id_is_omitted(
        self, tmp_path: Path, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        learned = tmp_path / "learned.json"
        learned.write_text(json.dumps({"patterns": [
            {
                "domain": "general",
                "description": "no id pattern",
                "pattern": "some pattern",
                "weight": 0.8,
                "success_count": 1,
                "injection_count": 0,
                "utilization_successes": 0,
                "last_seen": 0,
            },
        ]}))
        monkeypatch.setattr(_mod, "LEARNED_PATTERNS_FILE", learned)
        from omnicursor.pattern_cache import PatternCache
        fresh_cache = PatternCache()
        monkeypatch.setattr(_mod, "get_pattern_cache", lambda: fresh_cache)
        e = self._run_main_capture_log(monkeypatch, fake_sessions, conv_id="ids-003")
        for pid in e["injected_pattern_ids"]:
            assert pid != ""

    def test_injected_pattern_ids_respects_max_patterns(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run_main_capture_log(monkeypatch, fake_sessions, conv_id="ids-004")
        assert len(e["injected_pattern_ids"]) <= _mod.MAX_PATTERNS

    def test_send_event_payload_contains_injected_pattern_ids(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        send_calls: List[Dict] = []
        monkeypatch.setattr(_mod, "send_event", lambda topic, payload: send_calls.append({"topic": topic, "payload": payload}))
        monkeypatch.setattr(_mod, "log_event", lambda _: None)
        payload = {"prompt": "fix bug", "conversation_id": "ids-005"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        hook_event = next(
            (c for c in send_calls if c["topic"] == "onex.cmd.omnicursor.cursor-hook-event.v1"),
            None,
        )
        assert hook_event is not None
        assert "injected_pattern_ids" in hook_event["payload"]
        assert isinstance(hook_event["payload"]["injected_pattern_ids"], list)

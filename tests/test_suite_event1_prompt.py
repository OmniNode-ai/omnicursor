"""Event 1 — beforeSubmitPrompt: tests for user-prompt-submit.py.

After the W4 hook refactor this hook is block/observe-only: it classifies the
prompt, records relevant learned patterns for backend utilization scoring, emits
the hook event, and returns ``{"continue": true}``. It does NOT inject context
(Cursor's beforeSubmitPrompt cannot) — context injection moved to the sessionStart
and postToolUse hooks. So build_context / systemMessage / prior-session / handoff
nudge / recap tests are gone; see test_suite_session_start.py and
test_suite_post_tool_use.py for injection coverage.
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


_lib_common = _load("_common", _LIB / "_common.py")
_load("pattern_loader", _LIB / "pattern_loader.py")
_mod = _load("user_prompt_submit", _SCRIPTS / "user-prompt-submit.py")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate session state and make main() hermetic (no network, no socket)."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setattr(_mod, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(_mod, "ensure_dirs", lambda: None)
    monkeypatch.setattr(_mod, "log_event", lambda _: None)
    monkeypatch.setattr(_mod, "send_event", lambda *a, **k: False)
    monkeypatch.setattr(_mod, "ensure_daemon", lambda *a, **k: False)
    monkeypatch.setattr(_mod, "fetch_patterns", lambda *a, **k: [])
    return sessions


@pytest.fixture
def agents() -> List[Dict[str, Any]]:
    return _lib_common.load_agent_configs()


@pytest.fixture
def conv_id() -> str:
    return "test-conv-abc123"


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    payload: Dict[str, Any],
) -> str:
    """Run main() with *payload* on stdin; return captured stdout."""
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "stdout", out)
    _mod.main()
    return out.getvalue()


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
        name, _, _ = _mod.classify_prompt("foo bar baz", agents)
        assert name == "strong-agent"

    def test_agent_missing_activation_patterns_does_not_crash(self) -> None:
        name, score, _ = _mod.classify_prompt("debug this", [{"name": "broken"}])
        assert name == "polymorphic-agent"
        assert score == 0.0


# ---------------------------------------------------------------------------
# _estimate_complexity (gates delegation emit)
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


# ---------------------------------------------------------------------------
# Session-init fallback (for Cursor versions predating sessionStart)
# ---------------------------------------------------------------------------


class TestSessionIdentity:
    def test_init_creates_flag(self, fake_sessions: Path, conv_id: str) -> None:
        _mod._init_session_fallback(conv_id)
        assert (fake_sessions / conv_id / "session_initialized").exists()

    def test_init_writes_session_json(self, fake_sessions: Path, conv_id: str) -> None:
        _mod._init_session_fallback(conv_id)
        data = json.loads((fake_sessions / f"{conv_id}.json").read_text())
        assert data["conversation_id"] == conv_id
        assert "started_at" in data

    def test_init_idempotent(self, fake_sessions: Path, conv_id: str) -> None:
        _mod._init_session_fallback(conv_id)
        mtime = (fake_sessions / conv_id / "session_initialized").stat().st_mtime
        _mod._init_session_fallback(conv_id)
        assert (fake_sessions / conv_id / "session_initialized").stat().st_mtime == mtime

    def test_different_conv_ids_each_get_flag(self, fake_sessions: Path) -> None:
        _mod._init_session_fallback("session-A")
        _mod._init_session_fallback("session-B")
        assert (fake_sessions / "session-A" / "session_initialized").exists()
        assert (fake_sessions / "session-B" / "session_initialized").exists()

    def test_empty_conv_id_does_not_crash(self, fake_sessions: Path) -> None:
        _mod._init_session_fallback("")

    def test_main_triggers_session_init(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _run_main(monkeypatch, {"prompt": "fix bug", "conversation_id": "init-001"})
        assert (fake_sessions / "init-001" / "session_initialized").exists()


class TestDaemonEnsureFallback:
    """Portable daemon-ensure fallback: once per conversation, first prompt only."""

    def _run_with_tracking(
        self, monkeypatch: pytest.MonkeyPatch, payload: Dict[str, Any]
    ) -> List[bool]:
        calls: List[bool] = []
        monkeypatch.setattr(
            _mod, "ensure_daemon", lambda *a, **k: calls.append(True) or False
        )
        _run_main(monkeypatch, payload)
        return calls

    def test_first_prompt_triggers_ensure(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._run_with_tracking(
            monkeypatch, {"prompt": "fix bug", "conversation_id": "dae-001"}
        )
        assert len(calls) == 1

    def test_second_prompt_skips_ensure(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _run_main(monkeypatch, {"prompt": "fix bug", "conversation_id": "dae-002"})
        calls = self._run_with_tracking(
            monkeypatch, {"prompt": "and now refactor", "conversation_id": "dae-002"}
        )
        assert calls == []

    def test_background_agent_skips_ensure(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._run_with_tracking(
            monkeypatch,
            {
                "prompt": "fix bug",
                "conversation_id": "dae-003",
                "is_background_agent": True,
            },
        )
        assert calls == []

    def test_ensure_failure_never_blocks_prompt(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*a: Any, **k: Any) -> bool:
            raise RuntimeError("ensure exploded")

        monkeypatch.setattr(_mod, "ensure_daemon", _boom)
        out = _run_main(
            monkeypatch, {"prompt": "fix bug", "conversation_id": "dae-004"}
        )
        assert json.loads(out) == {"continue": True}


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

    def test_main_emits_correlation_id_in_log(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        _run_main(monkeypatch, {"prompt": "fix bug", "conversation_id": "corr-001"})
        assert len(events) == 1
        assert len(events[0]["correlation_id"]) == 12


class TestSessionCorrelationUpdate:
    def test_writes_correlation_to_current_json(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._update_session_correlation(conv_id, "abc123def456")
        data = json.loads((fake_sessions / "current.json").read_text())
        assert data["latest_correlation_id"] == "abc123def456"
        assert data["conversation_id"] == conv_id

    def test_overwrites_previous_correlation(
        self, fake_sessions: Path, conv_id: str
    ) -> None:
        _mod._update_session_correlation(conv_id, "first0000000a")
        _mod._update_session_correlation(conv_id, "second000000")
        data = json.loads((fake_sessions / "current.json").read_text())
        assert data["latest_correlation_id"] == "second000000"

    def test_main_writes_correlation_to_current_json(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _run_main(monkeypatch, {"prompt": "fix bug", "conversation_id": "cw-001"})
        data = json.loads((fake_sessions / "current.json").read_text())
        assert len(data["latest_correlation_id"]) == 12


# ---------------------------------------------------------------------------
# prompt_classified log event schema
# ---------------------------------------------------------------------------


class TestTypedEventSchema:
    def _event(
        self,
        monkeypatch: pytest.MonkeyPatch,
        prompt: str = "fix bug",
        conv_id: str = "schema-001",
    ) -> Dict:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        _run_main(
            monkeypatch,
            {"prompt": prompt, "conversation_id": conv_id, "generation_id": "gen-x"},
        )
        return events[0]

    def test_event_type_is_prompt_classified(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._event(monkeypatch)["event"] == "prompt_classified"

    def test_event_has_conversation_id(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._event(monkeypatch)["conversation_id"] == "schema-001"

    def test_event_has_matched_agent(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert "matched_agent" in self._event(monkeypatch)

    def test_event_has_score_float(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isinstance(self._event(monkeypatch)["score"], float)

    def test_event_has_patterns_injected_count(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._event(monkeypatch)
        assert isinstance(e["patterns_injected"], int)
        assert isinstance(e["injected_pattern_ids"], list)

    def test_event_has_delegation_required_bool(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isinstance(self._event(monkeypatch)["delegation_required"], bool)

    def test_prompt_snippet_truncated_at_100(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._event(monkeypatch, prompt="x" * 200)
        assert len(e["prompt_snippet"]) <= 100

    def test_event_has_hook_duration_ms(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isinstance(self._event(monkeypatch)["hook_duration_ms"], int)


# ---------------------------------------------------------------------------
# Output contract: block-only {"continue": true}, NEVER systemMessage
# ---------------------------------------------------------------------------


class TestContinueOutput:
    def test_main_outputs_continue_true(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = _run_main(monkeypatch, {"prompt": "fix bug", "conversation_id": "o-1"})
        assert json.loads(out) == {"continue": True}

    def test_main_does_not_emit_system_message(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = _run_main(monkeypatch, {"prompt": "fix bug", "conversation_id": "o-2"})
        parsed = json.loads(out)
        assert "systemMessage" not in parsed
        assert "additional_context" not in parsed

    def test_empty_stdin_still_outputs_continue(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        assert json.loads(out.getvalue()) == {"continue": True}


# ---------------------------------------------------------------------------
# Delegation request emission (backend learning, not injection)
# ---------------------------------------------------------------------------


class TestDelegationEmit:
    def _emitted(
        self, monkeypatch: pytest.MonkeyPatch, prompt: str
    ) -> List[str]:
        topics: List[str] = []
        monkeypatch.setattr(
            _mod, "send_event", lambda topic, payload: topics.append(topic) or True
        )
        _run_main(monkeypatch, {"prompt": prompt, "conversation_id": "d-1"})
        return topics

    def test_complex_prompt_emits_delegation_request(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        topics = self._emitted(
            monkeypatch,
            "Refactor the auth module and then migrate the database schema and "
            "integrate the new payment service across the whole codebase now",
        )
        assert "onex.cmd.omnicursor.node-delegation-request.v1" in topics

    def test_simple_prompt_does_not_emit_delegation(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        topics = self._emitted(monkeypatch, "fix typo")
        assert "onex.cmd.omnicursor.node-delegation-request.v1" not in topics

    def test_always_emits_cursor_hook_event(
        self, fake_sessions: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        topics = self._emitted(monkeypatch, "fix typo")
        assert "onex.cmd.omnicursor.cursor-hook-event.v1" in topics

"""Event 2 — beforeShellExecution: tests for shell-guard.py."""

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
_mod = _load("shell_guard", _SCRIPTS / "shell-guard.py")


# ---------------------------------------------------------------------------
# guard_command — HARD_BLOCK
# ---------------------------------------------------------------------------


class TestHardBlock:
    def test_hard_block_rm_rf_root(self) -> None:
        result = _mod.guard_command("rm -rf /")
        assert result["permission"] == "deny"

    def test_hard_block_rm_rf_home(self) -> None:
        result = _mod.guard_command("rm -rf ~/")
        assert result["permission"] == "deny"

    def test_hard_block_no_verify(self) -> None:
        result = _mod.guard_command("git commit --no-verify -m 'skip'")
        assert result["permission"] == "deny"

    def test_hard_block_mkfs(self) -> None:
        result = _mod.guard_command("mkfs.ext4 /dev/sdb1")
        assert result["permission"] == "deny"

    def test_hard_block_fork_bomb(self) -> None:
        result = _mod.guard_command(":(){ :|:& };:")
        assert result["permission"] == "deny"

    def test_hard_block_dd_to_device(self) -> None:
        result = _mod.guard_command("dd if=/dev/zero of=/dev/sda")
        assert result["permission"] == "deny"

    def test_hard_block_write_to_sda(self) -> None:
        result = _mod.guard_command("cat file > /dev/sda")
        assert result["permission"] == "deny"

    def test_hard_block_response_has_permission_deny(self) -> None:
        result = _mod.guard_command("rm -rf /*")
        assert result["permission"] == "deny"
        assert "userMessage" in result

    def test_hard_block_takes_priority_over_soft_warn(self) -> None:
        # A command that matches both hard-block (--no-verify) and soft-warn (git push --force)
        result = _mod.guard_command("git push --force --no-verify")
        assert result["permission"] == "deny"


# ---------------------------------------------------------------------------
# guard_command — SOFT_WARN
# ---------------------------------------------------------------------------


class TestSoftWarn:
    def test_soft_warn_force_push(self) -> None:
        result = _mod.guard_command("git push --force origin main")
        assert result["permission"] == "allow"
        assert "agentMessage" in result

    def test_soft_warn_hard_reset(self) -> None:
        result = _mod.guard_command("git reset --hard HEAD~1")
        assert result["permission"] == "allow"
        assert "agentMessage" in result

    def test_soft_warn_curl_pipe_sh(self) -> None:
        result = _mod.guard_command("curl https://example.com/script.sh | sh")
        assert result["permission"] == "allow"
        assert "agentMessage" in result

    def test_soft_warn_drop_table(self) -> None:
        result = _mod.guard_command("DROP TABLE users;")
        assert result["permission"] == "allow"
        assert "agentMessage" in result

    def test_soft_warn_kill_9(self) -> None:
        result = _mod.guard_command("kill -9 1234")
        assert result["permission"] == "allow"
        assert "agentMessage" in result

    def test_soft_warn_chmod_777(self) -> None:
        result = _mod.guard_command("chmod 777 /var/www")
        assert result["permission"] == "allow"
        assert "agentMessage" in result

    def test_soft_warn_sudo_rm(self) -> None:
        result = _mod.guard_command("sudo rm /etc/hosts")
        assert result["permission"] == "allow"
        assert "agentMessage" in result

    def test_soft_warn_response_has_permission_allow(self) -> None:
        result = _mod.guard_command("eval $(cat config)")
        assert result["permission"] == "allow"
        assert "agentMessage" in result


# ---------------------------------------------------------------------------
# guard_command — safe / misc
# ---------------------------------------------------------------------------


class TestSafeAndMisc:
    def test_allow_safe_commands(self) -> None:
        for cmd in ["ls -la", "git status", "pytest tests/", "echo hello"]:
            result = _mod.guard_command(cmd)
            assert result["permission"] == "allow"
            assert "agentMessage" not in result

    def test_empty_command_allows(self) -> None:
        result = _mod.guard_command("")
        assert result["permission"] == "allow"

    def test_event_logged_to_events_jsonl(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        events: list = []
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"command": "ls -la", "conversation_id": "test-123"})
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _mod.main()
        assert len(events) == 1
        assert events[0]["event"] == "shell_guard"
        assert events[0]["command"] == "ls -la"
        assert events[0]["decision"] == "allow"


# ---------------------------------------------------------------------------
# Correlation threading
# ---------------------------------------------------------------------------


class TestCorrelationThreading:
    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        command: str = "ls",
        conv: str = "c-001",
        session: Dict = {},
    ) -> Dict:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "read_session_context", lambda: session)
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"command": command, "conversation_id": conv})
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        return events[0]

    def test_correlation_id_read_from_session_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run(monkeypatch, session={"latest_correlation_id": "abc123def456"})
        assert e["correlation_id"] == "abc123def456"

    def test_missing_session_context_uses_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run(monkeypatch, session={})
        assert e["correlation_id"] == ""

    def test_correlation_id_present_on_deny_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run(
            monkeypatch,
            command="rm -rf /",
            session={"latest_correlation_id": "deadbeef1234"},
        )
        assert e["correlation_id"] == "deadbeef1234"
        assert e["decision"] == "deny"

    def test_correlation_id_present_on_warn_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run(
            monkeypatch,
            command="git push --force origin main",
            session={"latest_correlation_id": "warnid000001"},
        )
        assert e["correlation_id"] == "warnid000001"
        assert e["decision"] == "warn"

    def test_correlation_id_present_on_allow_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run(
            monkeypatch,
            command="pytest tests/",
            session={"latest_correlation_id": "allowid00001"},
        )
        assert e["correlation_id"] == "allowid00001"
        assert e["decision"] == "allow"

    def test_extra_session_fields_do_not_crash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        e = self._run(
            monkeypatch,
            session={
                "latest_correlation_id": "valid0000001",
                "conversation_id": "c-001",
                "started_at": "2026-04-14T00:00:00+00:00",
            },
        )
        assert e["correlation_id"] == "valid0000001"


# ---------------------------------------------------------------------------
# Typed event schema
# ---------------------------------------------------------------------------


class TestTypedEventSchema:
    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        command: str = "ls -la",
        conv: str = "s-001",
    ) -> Dict:
        events: List[Dict] = []
        monkeypatch.setattr(_mod, "read_session_context", lambda: {"latest_correlation_id": "test000abc12"})
        monkeypatch.setattr(_mod, "log_event", lambda e: events.append(e))
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"command": command, "conversation_id": conv})
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        _mod.main()
        return events[0]

    def test_event_type_is_shell_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["event"] == "shell_guard"

    def test_event_has_conversation_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["conversation_id"] == "s-001"

    def test_event_has_correlation_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["correlation_id"] == "test000abc12"

    def test_event_has_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["command"] == "ls -la"

    def test_event_has_decision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch)["decision"] == "allow"

    def test_event_has_hook_duration_ms(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch)
        assert "hook_duration_ms" in e and isinstance(e["hook_duration_ms"], int)

    def test_command_truncated_at_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        e = self._run(monkeypatch, command="x" * 600)
        assert len(e["command"]) == 500

    def test_deny_decision_logged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch, command="rm -rf /")["decision"] == "deny"

    def test_warn_decision_logged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch, command="git push --force origin main")["decision"] == "warn"

    def test_allow_decision_logged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch, command="git status")["decision"] == "allow"


# ---------------------------------------------------------------------------
# Phase 1 — DoD + dispatch claim
# ---------------------------------------------------------------------------


class TestDoDAndDispatch:
    def test_linear_done_denied_without_ci_passing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        (sessions / "conv-a.json").write_text(
            json.dumps({"conversation_id": "conv-a", "ci_passing": False}),
            encoding="utf-8",
        )
        monkeypatch.setenv("OMNICURSOR_DOD_BYPASS", "")
        r = _mod.guard_command(
            "linear issue update OMN-123 --state Done",
            conversation_id="conv-a",
            sessions_root=sessions,
        )
        assert r["permission"] == "deny"
        assert "DoD" in r.get("userMessage", "")

    def test_linear_done_allowed_when_ci_passing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        (sessions / "conv-b.json").write_text(
            json.dumps({"ci_passing": True}),
            encoding="utf-8",
        )
        r = _mod.guard_command(
            "linear issue update OMN-123 --state Done",
            conversation_id="conv-b",
            sessions_root=sessions,
        )
        assert r["permission"] == "allow"

    def test_dod_bypass_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        (sessions / "conv-c.json").write_text(json.dumps({"ci_passing": False}))
        monkeypatch.setenv("OMNICURSOR_DOD_BYPASS", "1")
        r = _mod.guard_command(
            "linear issue update OMN-123 --state Done",
            conversation_id="conv-c",
            sessions_root=sessions,
        )
        assert r["permission"] == "allow"
        monkeypatch.delenv("OMNICURSOR_DOD_BYPASS", raising=False)

    def test_dispatch_claim_enforced_when_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = tmp_path / "sessions"
        (sessions / "conv-d").mkdir(parents=True)
        monkeypatch.setattr(
            _mod,
            "_load_dod_config",
            lambda: {
                "dod_enabled": False,
                "dod_linear_transition_regex": "",
                "dispatch_enabled": True,
                "dispatch_claim_regexes": [r"(?i)^git\s+commit\s+--amend\b"],
            },
        )
        monkeypatch.delenv("OMNICURSOR_DISPATCH_BYPASS", raising=False)
        r = _mod.guard_command(
            "git commit --amend --no-edit",
            conversation_id="conv-d",
            sessions_root=sessions,
        )
        assert r["permission"] == "deny"
        (sessions / "conv-d" / "dispatch_claim").touch()
        r2 = _mod.guard_command(
            "git commit --amend --no-edit",
            conversation_id="conv-d",
            sessions_root=sessions,
        )
        assert r2["permission"] == "allow"

"""A6 — kill-switch (env + file marker) + per-hook mask across all 7 hooks.

The gate must short-circuit FIRST — before reading stdin, daemon-ensure,
pattern fetch/sync, local logging, emission, or injection writes. These tests
assert side effects (recorded calls, files on disk), not just exit behavior.

Disabled outputs are benign: ``shell-guard`` fails OPEN (``allow`` — a disabled
guard never blocks the user), ``user-prompt-submit`` returns
``{"continue": true}``, everything else returns ``{}``.
"""

from __future__ import annotations

import importlib.util as _ilu
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / ".cursor" / "hooks" / "lib"
_SCRIPTS = _ROOT / ".cursor" / "hooks" / "scripts"


def _load(name: str, path: Path) -> Any:
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_common = _load("_common", _LIB / "_common.py")
_session_start = _load("ks_session_start", _SCRIPTS / "session-start.py")
_prompt = _load("ks_user_prompt_submit", _SCRIPTS / "user-prompt-submit.py")
_shell = _load("ks_shell_guard", _SCRIPTS / "shell-guard.py")
_edit = _load("ks_post_edit", _SCRIPTS / "post-edit.py")
_tool = _load("ks_post_tool_use", _SCRIPTS / "post-tool-use.py")
_stop = _load("ks_stop", _SCRIPTS / "stop.py")
_session_end = _load("ks_session_end", _SCRIPTS / "session-end.py")


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Sandboxed HOME + neither kill-switch mechanism set."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OMNICURSOR_HOOKS_DISABLE", raising=False)
    monkeypatch.delenv("OMNICURSOR_HOOKS_MASK", raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# hooks_disabled() — the two escape hatches (donor: omniclaude server.py)
# ---------------------------------------------------------------------------


class TestHooksDisabled:
    def test_default_is_enabled(self, clean_env: Path) -> None:
        assert _common.hooks_disabled() is False

    def test_env_1_disables(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_DISABLE", "1")
        assert _common.hooks_disabled() is True

    @pytest.mark.parametrize("value", ["0", "", "true", "yes", "2"])
    def test_env_non_1_values_do_not_disable(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        # Exact-"1" semantics, mirroring the omniclaude donor.
        monkeypatch.setenv("OMNICURSOR_HOOKS_DISABLE", value)
        assert _common.hooks_disabled() is False

    def test_file_marker_disables(self, clean_env: Path) -> None:
        marker_dir = clean_env / ".omnicursor"
        marker_dir.mkdir()
        (marker_dir / "hooks-disabled").touch()
        assert _common.hooks_disabled() is True

    def test_marker_is_resolved_at_call_time(self, clean_env: Path) -> None:
        # No marker → enabled; create it → disabled; remove it → enabled again.
        assert _common.hooks_disabled() is False
        marker_dir = clean_env / ".omnicursor"
        marker_dir.mkdir()
        marker = marker_dir / "hooks-disabled"
        marker.touch()
        assert _common.hooks_disabled() is True
        marker.unlink()
        assert _common.hooks_disabled() is False


# ---------------------------------------------------------------------------
# hook_enabled() — OMNICURSOR_HOOKS_MASK allowlist
# ---------------------------------------------------------------------------

_ALL_HOOK_NAMES = [
    "session-start",
    "prompt",
    "shell",
    "edit",
    "tool",
    "stop",
    "session-end",
]


class TestHookMask:
    def test_unset_mask_enables_all(self, clean_env: Path) -> None:
        for name in _ALL_HOOK_NAMES:
            assert _common.hook_enabled(name) is True, name

    @pytest.mark.parametrize("mask", ["", "   "])
    def test_blank_mask_means_unset(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch, mask: str
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", mask)
        for name in _ALL_HOOK_NAMES:
            assert _common.hook_enabled(name) is True, name

    def test_mask_enables_exactly_the_named_hooks(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", "prompt,shell")
        assert _common.hook_enabled("prompt") is True
        assert _common.hook_enabled("shell") is True
        for name in ("session-start", "edit", "tool", "stop", "session-end"):
            assert _common.hook_enabled(name) is False, name

    @pytest.mark.parametrize(
        ("alias", "canonical"),
        [
            ("session_start", "session-start"),
            ("sessionStart", "session-start"),
            ("start", "session-start"),
            ("user-prompt-submit", "prompt"),
            ("beforeSubmitPrompt", "prompt"),
            ("shell-guard", "shell"),
            ("beforeShellExecution", "shell"),
            ("post-edit", "edit"),
            ("afterFileEdit", "edit"),
            ("post-tool-use", "tool"),
            ("postToolUse", "tool"),
            ("sessionEnd", "session-end"),
            ("end", "session-end"),
        ],
    )
    def test_mask_accepts_aliases(
        self,
        clean_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        alias: str,
        canonical: str,
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", alias)
        assert _common.hook_enabled(canonical) is True

    def test_mask_tolerates_spaces(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", " prompt , shell ")
        assert _common.hook_enabled("prompt") is True
        assert _common.hook_enabled("shell") is True
        assert _common.hook_enabled("stop") is False

    def test_unknown_mask_tokens_enable_nothing(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", "no-such-hook")
        for name in _ALL_HOOK_NAMES:
            assert _common.hook_enabled(name) is False, name

    def test_kill_switch_overrides_mask(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", "prompt")
        monkeypatch.setenv("OMNICURSOR_HOOKS_DISABLE", "1")
        assert _common.hook_enabled("prompt") is False


# ---------------------------------------------------------------------------
# Per-hook short-circuit — the gate precedes EVERY side effect
# ---------------------------------------------------------------------------

# (hook_key, module, side-effect functions bound in the module namespace,
#  benign stdout when disabled)
_HOOK_SPECS: List[Tuple[str, Any, List[str], Dict[str, Any]]] = [
    (
        "session-start",
        _session_start,
        [
            "read_stdin",
            "log_event",
            "send_event",
            "ensure_daemon",
            "sync_learned_patterns",
            "fetch_patterns",
            "_init_session",
        ],
        {},
    ),
    (
        "prompt",
        _prompt,
        [
            "read_stdin",
            "log_event",
            "send_event",
            "ensure_daemon",
            "fetch_patterns",
            "load_agent_configs",
            "_init_session_fallback",
            "_update_session_correlation",
            "_bump_session_prompt_timestamp",
        ],
        {"continue": True},
    ),
    (
        "shell",
        _shell,
        ["read_stdin", "log_event", "send_event", "guard_command"],
        {"permission": "allow"},
    ),
    ("edit", _edit, ["read_stdin", "log_event", "send_event", "handle_edit"], {}),
    ("tool", _tool, ["read_stdin", "log_event", "send_event", "fetch_patterns"], {}),
    (
        "stop",
        _stop,
        [
            "read_stdin",
            "log_event",
            "send_event",
            "aggregate_session",
            "write_session_patterns",
            "write_session_outcome",
        ],
        {},
    ),
    ("session-end", _session_end, ["read_stdin", "log_event", "send_event"], {}),
]

_SPEC_IDS = [spec[0] for spec in _HOOK_SPECS]


def _recorder(calls: List[str], name: str) -> Callable[..., Dict[str, Any]]:
    def _rec(*_a: Any, **_k: Any) -> Dict[str, Any]:
        calls.append(name)
        return {}

    return _rec


def _run_instrumented(
    mod: Any, side_effects: List[str], monkeypatch: pytest.MonkeyPatch
) -> Tuple[List[str], Dict[str, Any]]:
    calls: List[str] = []
    for name in side_effects:
        monkeypatch.setattr(mod, name, _recorder(calls, name))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    mod.main()
    return calls, json.loads(out.getvalue())


@pytest.mark.parametrize(
    ("hook_key", "mod", "side_effects", "benign"), _HOOK_SPECS, ids=_SPEC_IDS
)
class TestKillSwitchShortCircuit:
    def test_env_disable_no_side_effects_benign_output(
        self,
        hook_key: str,
        mod: Any,
        side_effects: List[str],
        benign: Dict[str, Any],
        clean_env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_DISABLE", "1")
        calls, out = _run_instrumented(mod, side_effects, monkeypatch)
        assert calls == []  # not even read_stdin ran
        assert out == benign

    def test_file_marker_disable_no_side_effects_benign_output(
        self,
        hook_key: str,
        mod: Any,
        side_effects: List[str],
        benign: Dict[str, Any],
        clean_env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        marker_dir = clean_env / ".omnicursor"
        marker_dir.mkdir()
        (marker_dir / "hooks-disabled").touch()
        calls, out = _run_instrumented(mod, side_effects, monkeypatch)
        assert calls == []
        assert out == benign

    def test_mask_excluding_this_hook_short_circuits(
        self,
        hook_key: str,
        mod: Any,
        side_effects: List[str],
        benign: Dict[str, Any],
        clean_env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", "no-such-hook")
        calls, out = _run_instrumented(mod, side_effects, monkeypatch)
        assert calls == []
        assert out == benign


class TestMaskEnablesNamedHooks:
    """The allowlist enables exactly the named hooks — the named ones still run."""

    def test_masked_in_session_end_still_emits(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", "session-end")
        calls, out = _run_instrumented(
            _session_end, ["read_stdin", "log_event", "send_event"], monkeypatch
        )
        assert "read_stdin" in calls
        assert "send_event" in calls
        assert out == {}

    def test_masked_in_shell_still_guards(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", "shell")
        calls: List[str] = []
        monkeypatch.setattr(
            _shell, "read_stdin", lambda: {"command": "rm -rf /", "conversation_id": "c-1"}
        )
        monkeypatch.setattr(_shell, "read_session_context", lambda: {})
        monkeypatch.setattr(_shell, "log_event", _recorder(calls, "log_event"))
        monkeypatch.setattr(_shell, "send_event", _recorder(calls, "send_event"))
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _shell.main()
        response = json.loads(out.getvalue())
        # The guard genuinely ran: a HARD_BLOCK command is still denied.
        assert response["permission"] == "deny"
        assert "log_event" in calls

    def test_masked_out_shell_fails_open_even_for_deny_commands(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OMNICURSOR_HOOKS_MASK", "prompt")
        calls, out = _run_instrumented(
            _shell, ["read_stdin", "log_event", "send_event", "guard_command"], monkeypatch
        )
        assert calls == []
        assert out == {"permission": "allow"}


class TestDisabledShellGuardFailsOpen:
    def test_disabled_guard_allows_hard_block_command(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Even a command the guard would deny gets "allow" when disabled: the
        # kill-switch turns off side effects; it must never block the user.
        monkeypatch.setenv("OMNICURSOR_HOOKS_DISABLE", "1")
        monkeypatch.setattr(
            _shell, "read_stdin", lambda: {"command": "rm -rf /", "conversation_id": "c-1"}
        )
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        _shell.main()
        assert json.loads(out.getvalue()) == {"permission": "allow"}


# ---------------------------------------------------------------------------
# Structural guard — the gate is the FIRST statement of main() in all 7 scripts
# (programmatic form of PHASE_0_RESULTS §6 A6(b))
# ---------------------------------------------------------------------------


class TestGatePrecedesSideEffectsInSource:
    @pytest.mark.parametrize(
        "script", sorted(_SCRIPTS.glob("*.py")), ids=lambda p: p.name
    )
    def test_hook_enabled_gate_precedes_read_stdin(self, script: Path) -> None:
        src = script.read_text(encoding="utf-8")
        body = src[src.index("def main(") :]
        gate = body.index("hook_enabled(")
        stdin = body.index("read_stdin(")
        assert gate < stdin, f"{script.name}: kill-switch gate must precede read_stdin"


# ---------------------------------------------------------------------------
# End-to-end (subprocess): disabled hooks exit 0, print benign JSON, write
# NOTHING under a sandboxed HOME
# ---------------------------------------------------------------------------

_BENIGN_BY_SCRIPT: Dict[str, Dict[str, Any]] = {
    "session-start.py": {},
    "user-prompt-submit.py": {"continue": True},
    "shell-guard.py": {"permission": "allow"},
    "post-edit.py": {},
    "post-tool-use.py": {},
    "stop.py": {},
    "session-end.py": {},
}


class TestDisabledSubprocessEndToEnd:
    @pytest.mark.parametrize("script_name", sorted(_BENIGN_BY_SCRIPT), ids=str)
    def test_disabled_hook_exits_zero_and_writes_nothing(
        self, tmp_path: Path, script_name: str
    ) -> None:
        env = {
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
            "OMNICURSOR_HOOKS_DISABLE": "1",
        }
        proc = subprocess.run(
            [sys.executable, str(_SCRIPTS / script_name)],
            input='{"conversation_id": "c-e2e", "command": "rm -rf /", "prompt": "hi"}',
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == _BENIGN_BY_SCRIPT[script_name]
        # Zero side effects on disk: no ~/.omnicursor tree, no events.jsonl,
        # no sessions/, no learned_patterns.json.
        assert not (tmp_path / ".omnicursor").exists()

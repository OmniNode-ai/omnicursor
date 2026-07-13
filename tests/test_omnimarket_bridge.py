"""Tests for omnicursor.omnimarket_bridge — subprocess mocked, no real Omnimarket."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from omnicursor import omnimarket_bridge

_VALID_STATE = {
    "correlation_id": "00000000-0000-0000-0000-000000000001",
    "current_phase": "init",
    "consecutive_failures": 0,
    "dry_run": False,
    "iteration_count": 0,
    "max_iterations": 10,
    "issues_found": 0,
    "issues_fixed": 0,
}


class _FakeProc:
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class _SubprocessSpy:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        raise_timeout: bool = False,
    ) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._stdout = stdout
        self._stderr = stderr
        self._returncode = returncode
        self._raise_timeout = raise_timeout

    def __call__(self, cmd: List[str], **kwargs: Any) -> _FakeProc:
        self.calls.append({"cmd": cmd, **kwargs})
        if self._raise_timeout:
            raise subprocess.TimeoutExpired(cmd, timeout=300)
        return _FakeProc(
            stdout=self._stdout,
            stderr=self._stderr,
            returncode=self._returncode,
        )


@pytest.fixture()
def fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "omnimarket-main"
    root.mkdir()
    return root


def _patch_root(monkeypatch: pytest.MonkeyPatch, root: Optional[Path]) -> None:
    monkeypatch.setattr(omnimarket_bridge, "_resolve_root", lambda: root)


def _patch_subprocess(monkeypatch: pytest.MonkeyPatch, spy: _SubprocessSpy) -> None:
    monkeypatch.setattr(omnimarket_bridge.subprocess, "run", spy)


# --- success path ---


def test_success_parses_json(monkeypatch: pytest.MonkeyPatch, fake_root: Path) -> None:
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review()

    assert result["ok"] is True
    assert result["state"] == _VALID_STATE
    assert result["error"] is None
    assert result["returncode"] == 0


# --- CLI flag forwarding ---


def test_dry_run_flag(monkeypatch: pytest.MonkeyPatch, fake_root: Path) -> None:
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_local_review(dry_run=True)

    assert "--dry-run" in spy.calls[0]["cmd"]


def test_max_iterations_flag(monkeypatch: pytest.MonkeyPatch, fake_root: Path) -> None:
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_local_review(max_iterations=5)

    cmd = spy.calls[0]["cmd"]
    idx = cmd.index("--max-iterations")
    assert cmd[idx + 1] == "5"


def test_required_clean_runs_flag(
    monkeypatch: pytest.MonkeyPatch, fake_root: Path
) -> None:
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_local_review(required_clean_runs=3)

    cmd = spy.calls[0]["cmd"]
    idx = cmd.index("--required-clean-runs")
    assert cmd[idx + 1] == "3"


def test_all_defaults(monkeypatch: pytest.MonkeyPatch, fake_root: Path) -> None:
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_local_review()

    cmd = spy.calls[0]["cmd"]
    assert "--dry-run" not in cmd
    assert "--max-iterations" not in cmd
    assert "--required-clean-runs" not in cmd


# --- root resolution ---


def test_missing_root_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_root(monkeypatch, None)
    monkeypatch.delenv("OMNIMARKET_ROOT", raising=False)

    result = omnimarket_bridge.run_local_review()

    assert result["ok"] is False
    assert "OMNIMARKET_ROOT" in (result["error"] or "")
    assert result["state"] is None


def test_env_root_takes_priority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_root = tmp_path / "env-checkout"
    env_root.mkdir()
    fallback = tmp_path / "omnimarket-main"
    fallback.mkdir()

    monkeypatch.setenv("OMNIMARKET_ROOT", str(env_root))
    monkeypatch.setattr(omnimarket_bridge, "_find_repo_root", lambda: tmp_path)

    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review()

    assert result["cwd"] == str(env_root)


def test_fallback_to_repo_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fallback = tmp_path / "omnimarket-main"
    fallback.mkdir()

    monkeypatch.delenv("OMNIMARKET_ROOT", raising=False)
    monkeypatch.setattr(omnimarket_bridge, "_find_repo_root", lambda: tmp_path)

    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review()

    assert result["cwd"] == str(fallback)


# --- failure paths ---


def test_nonzero_returncode(monkeypatch: pytest.MonkeyPatch, fake_root: Path) -> None:
    spy = _SubprocessSpy(stdout="", stderr="ImportError: no module", returncode=1)
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review()

    assert result["ok"] is False
    assert result["returncode"] == 1
    assert "ImportError" in (result["error"] or "")


def test_invalid_json_stdout(monkeypatch: pytest.MonkeyPatch, fake_root: Path) -> None:
    spy = _SubprocessSpy(stdout="not json at all")
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review()

    assert result["ok"] is False
    assert result["state"] is None
    assert "JSON parse error" in (result["error"] or "")


def test_timeout(monkeypatch: pytest.MonkeyPatch, fake_root: Path) -> None:
    spy = _SubprocessSpy(raise_timeout=True)
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review()

    assert result["ok"] is False
    assert "timed out" in (result["error"] or "")


# --- debug fields ---


def test_custom_python_env(monkeypatch: pytest.MonkeyPatch, fake_root: Path) -> None:
    monkeypatch.setenv("OMNIMARKET_PYTHON", "/custom/bin/python")
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review()

    assert result["python"] == "/custom/bin/python"
    assert spy.calls[0]["cmd"][0] == "/custom/bin/python"


def test_cwd_is_omnimarket_root(
    monkeypatch: pytest.MonkeyPatch, fake_root: Path
) -> None:
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review()

    assert result["cwd"] == str(fake_root)
    assert spy.calls[0]["cwd"] == str(fake_root)


def test_command_field_populated(
    monkeypatch: pytest.MonkeyPatch, fake_root: Path
) -> None:
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    result = omnimarket_bridge.run_local_review(dry_run=True, max_iterations=3)

    assert "-m" in result["command"]
    assert "omnimarket.nodes.node_local_review" in result["command"]
    assert "--dry-run" in result["command"]


# --- PYTHONPATH injection ---


def test_subprocess_receives_env_with_pythonpath(
    monkeypatch: pytest.MonkeyPatch, fake_root: Path
) -> None:
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_local_review()

    call = spy.calls[0]
    assert "env" in call
    assert "PYTHONPATH" in call["env"]
    assert str(fake_root / "src") in call["env"]["PYTHONPATH"]


def test_pythonpath_includes_root_src(
    monkeypatch: pytest.MonkeyPatch, fake_root: Path
) -> None:
    monkeypatch.delenv("PYTHONPATH", raising=False)
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_local_review()

    pythonpath = spy.calls[0]["env"]["PYTHONPATH"]
    assert pythonpath == str(fake_root / "src")


def test_run_ticket_pipeline_uses_positional_ticket_id(
    monkeypatch: pytest.MonkeyPatch, fake_root: Path
) -> None:
    spy = _SubprocessSpy(stdout="{}")
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_ticket_pipeline(ticket_id="OMN-47")

    cmd = spy.calls[0]["cmd"]
    assert "omnimarket.nodes.node_ticket_pipeline" in cmd
    assert "--ticket-id" not in cmd
    assert cmd[-1] == "OMN-47"


def test_run_ticket_pipeline_optional_flags_before_positional_id(
    monkeypatch: pytest.MonkeyPatch, fake_root: Path
) -> None:
    spy = _SubprocessSpy(stdout="{}")
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_ticket_pipeline(
        ticket_id="OMN-42",
        skip_test_iterate=True,
        dry_run=True,
    )

    cmd = spy.calls[0]["cmd"]
    assert "--ticket-id" not in cmd
    assert "--skip-test-iterate" in cmd
    assert "--dry-run" in cmd
    assert (
        cmd.index("--skip-test-iterate") < cmd.index("--dry-run") < cmd.index("OMN-42")
    )
    assert cmd[-1] == "OMN-42"


def test_existing_pythonpath_preserved(
    monkeypatch: pytest.MonkeyPatch, fake_root: Path
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/existing/lib")
    spy = _SubprocessSpy(stdout=json.dumps(_VALID_STATE))
    _patch_root(monkeypatch, fake_root)
    _patch_subprocess(monkeypatch, spy)

    omnimarket_bridge.run_local_review()

    pythonpath = spy.calls[0]["env"]["PYTHONPATH"]
    parts = pythonpath.split(os.pathsep)
    assert parts[0] == str(fake_root / "src")
    assert "/existing/lib" in parts

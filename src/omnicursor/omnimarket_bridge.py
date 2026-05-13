"""Subprocess bridge to a local Omnimarket checkout.

Invokes ``python -m omnimarket.nodes.node_local_review`` in a resolved
Omnimarket root directory.  All failures are expressed in the return dict —
no exceptions are raised to callers.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

_TIMEOUT_SECONDS = 300


class BridgeResult(TypedDict):
    ok: bool
    returncode: int
    state: Optional[Dict[str, Any]]
    stderr: str
    error: Optional[str]
    command: List[str]
    cwd: Optional[str]
    python: str


def _find_repo_root() -> Optional[Path]:
    path = Path(__file__).resolve().parent
    while path != path.parent:
        if (path / ".git").exists():
            return path
        path = path.parent
    return None


def _resolve_root() -> Optional[Path]:
    env = os.environ.get("OMNIMARKET_ROOT")
    if env:
        p = Path(env)
        if p.is_dir():
            return p
        return None

    repo = _find_repo_root()
    if repo:
        fallback = repo / "omnimarket-main"
        if fallback.is_dir():
            return fallback
    return None


def _resolve_python() -> str:
    return os.environ.get("OMNIMARKET_PYTHON", sys.executable)


def _error_result(
    error: str, *, python: str = "", command: Optional[List[str]] = None
) -> BridgeResult:
    return BridgeResult(
        ok=False,
        returncode=-1,
        state=None,
        stderr="",
        error=error,
        command=command or [],
        cwd=None,
        python=python,
    )


def run_local_review(
    *,
    dry_run: bool = False,
    max_iterations: Optional[int] = None,
    required_clean_runs: Optional[int] = None,
) -> BridgeResult:
    root = _resolve_root()
    python = _resolve_python()

    if root is None:
        env_val = os.environ.get("OMNIMARKET_ROOT", "")
        if env_val:
            return _error_result(
                f"OMNIMARKET_ROOT={env_val} is not a directory. "
                "Point it to a local omnimarket checkout.",
                python=python,
            )
        return _error_result(
            "Omnimarket checkout not found. Set OMNIMARKET_ROOT to the "
            "absolute path of a local omnimarket checkout, or place it at "
            "omnimarket-main/ in the OmniCursor repo root.",
            python=python,
        )

    cmd: List[str] = [python, "-m", "omnimarket.nodes.node_local_review"]
    if dry_run:
        cmd.append("--dry-run")
    if max_iterations is not None:
        cmd.extend(["--max-iterations", str(max_iterations)])
    if required_clean_runs is not None:
        cmd.extend(["--required-clean-runs", str(required_clean_runs)])

    cwd = str(root)

    env = os.environ.copy()
    src_dir = str(root / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing}" if existing else src_dir

    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return BridgeResult(
            ok=False,
            returncode=-1,
            state=None,
            stderr="",
            error=f"Subprocess timed out after {_TIMEOUT_SECONDS}s",
            command=cmd,
            cwd=cwd,
            python=python,
        )

    state: Optional[Dict[str, Any]] = None
    parse_error: Optional[str] = None
    try:
        state = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        snippet = proc.stdout[:200] if proc.stdout else "(empty)"
        parse_error = f"JSON parse error: {exc}. Stdout: {snippet}"

    if proc.returncode != 0:
        return BridgeResult(
            ok=False,
            returncode=proc.returncode,
            state=state,
            stderr=proc.stderr,
            error=proc.stderr.strip() or parse_error or f"Exit code {proc.returncode}",
            command=cmd,
            cwd=cwd,
            python=python,
        )

    if parse_error:
        return BridgeResult(
            ok=False,
            returncode=proc.returncode,
            state=None,
            stderr=proc.stderr,
            error=parse_error,
            command=cmd,
            cwd=cwd,
            python=python,
        )

    return BridgeResult(
        ok=True,
        returncode=0,
        state=state,
        stderr=proc.stderr,
        error=None,
        command=cmd,
        cwd=cwd,
        python=python,
    )


def _run_node(
    module: str,
    args: List[str],
    *,
    timeout: int = _TIMEOUT_SECONDS,
) -> BridgeResult:
    """Generic helper — runs any omnimarket node module with the given args."""
    root = _resolve_root()
    python = _resolve_python()

    if root is None:
        env_val = os.environ.get("OMNIMARKET_ROOT", "")
        if env_val:
            return _error_result(
                f"OMNIMARKET_ROOT={env_val} is not a directory.",
                python=python,
            )
        return _error_result(
            "Omnimarket checkout not found. Set OMNIMARKET_ROOT to the "
            "absolute path of a local omnimarket checkout.",
            python=python,
        )

    cmd = [python, "-m", module, *args]
    cwd = str(root)
    env = os.environ.copy()
    src_dir = str(root / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing}" if existing else src_dir

    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return BridgeResult(
            ok=False, returncode=-1, state=None, stderr="",
            error=f"Subprocess timed out after {timeout}s",
            command=cmd, cwd=cwd, python=python,
        )

    state: Optional[Dict[str, Any]] = None
    parse_error: Optional[str] = None
    try:
        state = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        snippet = proc.stdout[:200] if proc.stdout else "(empty)"
        parse_error = f"JSON parse error: {exc}. Stdout: {snippet}"

    if proc.returncode != 0:
        return BridgeResult(
            ok=False, returncode=proc.returncode, state=state, stderr=proc.stderr,
            error=proc.stderr.strip() or parse_error or f"Exit code {proc.returncode}",
            command=cmd, cwd=cwd, python=python,
        )
    if parse_error:
        return BridgeResult(
            ok=False, returncode=proc.returncode, state=None, stderr=proc.stderr,
            error=parse_error, command=cmd, cwd=cwd, python=python,
        )
    return BridgeResult(
        ok=True, returncode=0, state=state, stderr=proc.stderr,
        error=None, command=cmd, cwd=cwd, python=python,
    )


def run_ticket_pipeline(
    *,
    ticket_id: str,
    skip_test_iterate: bool = False,
    dry_run: bool = False,
) -> BridgeResult:
    """Run node_ticket_pipeline for a single Linear ticket.

    Drives the full pipeline: IMPLEMENT → LOCAL_REVIEW → CREATE_PR →
    TEST_ITERATE → CI_WATCH → PR_REVIEW → AUTO_MERGE → DONE.

    Returns BridgeResult with state keys: final_phase, pr_number.
    Timeout: 10 minutes (pipeline includes CI wait).
    """
    # omnimarket node_ticket_pipeline: optional flags then positional ticket_id.
    args: List[str] = []
    if skip_test_iterate:
        args.append("--skip-test-iterate")
    if dry_run:
        args.append("--dry-run")
    args.append(ticket_id)
    return _run_node(
        "omnimarket.nodes.node_ticket_pipeline",
        args,
        timeout=600,
    )


def run_ci_watch(
    *,
    pr_number: int,
    repo: str,
    correlation_id: str,
    timeout_minutes: int = 60,
    max_fix_cycles: int = 3,
    dry_run: bool = False,
) -> BridgeResult:
    """Run node_ci_watch — polls GitHub Actions for a PR and auto-fixes failures.

    Returns BridgeResult with state keys: terminal_status, failed_checks,
    failure_summary.
    Timeout: timeout_minutes + 5 minute buffer.
    """
    args = [
        "--pr-number", str(pr_number),
        "--repo", repo,
        "--correlation-id", correlation_id,
        "--timeout-minutes", str(timeout_minutes),
        "--max-fix-cycles", str(max_fix_cycles),
    ]
    if dry_run:
        args.append("--dry-run")
    return _run_node(
        "omnimarket.nodes.node_ci_watch",
        args,
        timeout=(timeout_minutes + 5) * 60,
    )

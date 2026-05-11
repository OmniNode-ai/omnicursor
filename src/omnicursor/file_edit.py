# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""File-edit business logic shared by node_cursor_file_edit_effect.

Extracted from .cursor/hooks/scripts/post-edit.py. The hook script retains
its own copy for stdlib-only execution; this module is the importable version
for node handlers and tests.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[2]

_EXTENSION_MAP: Dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
}


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _resolve_ruff_command() -> list[str]:
    """Return a ruff command that works even when Cursor does not inherit venv PATH."""
    candidates = [
        _REPO_ROOT / ".venv" / "bin" / "ruff",
        _REPO_ROOT / ".venv" / "Scripts" / "ruff.exe",
    ]
    for candidate in candidates:
        if _is_executable(candidate):
            return [str(candidate)]

    found = shutil.which("ruff")
    if found:
        return [found]

    return [sys.executable, "-m", "ruff"]


def detect_language(path: str) -> str:
    """Return a language label based on file extension."""
    ext = Path(path).suffix.lower()
    return _EXTENSION_MAP.get(ext, "other")


def run_ruff_check(file_path: str) -> int:
    """Run ``ruff check`` diagnostically on *file_path*.

    Returns the number of findings. Never passes ``--fix``. Never modifies files.
    """
    try:
        cmd = [*_resolve_ruff_command(), "check", file_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (result.stdout or "").strip()
        return len([ln for ln in output.splitlines() if ln.strip()])
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 0


def run_tsc_check(file_path: str) -> int:
    """Run ``tsc --noEmit`` diagnostically on *file_path*.

    Returns the number of TypeScript error lines. Never modifies files.
    """
    try:
        result = subprocess.run(
            ["tsc", "--noEmit", file_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = (result.stdout or "").strip()
        return len([ln for ln in output.splitlines() if ln.strip() and "error TS" in ln])
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 0


def handle_edit(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process an afterFileEdit event dict and return a result dict."""
    file_path = event.get("file_path", "")
    edits = event.get("edits", [])
    conversation_id = event.get("conversation_id", "")

    language = detect_language(file_path) if file_path else "other"
    edit_count = len(edits) if isinstance(edits, list) else 0

    ruff_findings = 0
    if language == "python" and file_path:
        ruff_findings = run_ruff_check(file_path)

    tsc_findings = 0
    if language == "typescript" and file_path:
        tsc_findings = run_tsc_check(file_path)

    return {
        "event": "file_edited",
        "conversation_id": conversation_id,
        "file_path": file_path[:500] if file_path else "",
        "edit_count": edit_count,
        "language": language,
        "ruff_findings": ruff_findings,
        "tsc_findings": tsc_findings,
    }

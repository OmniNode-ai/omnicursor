# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""File-edit business logic shared by node_cursor_file_edit_effect.

Extracted from .cursor/hooks/scripts/post-edit.py. The hook script retains
its own copy for stdlib-only execution; this module is the importable version
for node handlers and tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict

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


def detect_language(path: str) -> str:
    """Return a language label based on file extension."""
    ext = Path(path).suffix.lower()
    return _EXTENSION_MAP.get(ext, "other")


def run_ruff_check(file_path: str) -> int:
    """Run ``ruff check`` diagnostically on *file_path*.

    Returns the number of findings. Never passes ``--fix``. Never modifies files.
    """
    try:
        result = subprocess.run(
            ["ruff", "check", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (result.stdout or "").strip()
        return len([ln for ln in output.splitlines() if ln.strip()])
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

    return {
        "event": "file_edited",
        "conversation_id": conversation_id,
        "file_path": file_path[:500] if file_path else "",
        "edit_count": edit_count,
        "language": language,
        "ruff_findings": ruff_findings,
    }

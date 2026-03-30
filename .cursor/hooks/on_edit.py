"""afterFileEdit hook — log edits and run diagnostic ruff on Python files.

Informational only — Cursor ignores stdout. Never modifies files.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import OMNICURSOR_DIR, ensure_dirs, log_event, read_stdin, write_stdout


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Ruff diagnostics (read-only — never --fix)
# ---------------------------------------------------------------------------

LINT_LOG = OMNICURSOR_DIR / "lint.jsonl"


def _run_ruff_check(file_path: str) -> None:
    """Run ruff check (diagnostic only) and log any issues found."""
    try:
        result = subprocess.run(
            ["ruff", "check", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (result.stdout or "").strip()
        if output:
            ensure_dirs()
            import datetime

            entry = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "file_path": file_path,
                "issues": output,
                "returncode": result.returncode,
            }
            with LINT_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # ruff not installed or timed out — skip silently
        pass


# ---------------------------------------------------------------------------
# Edit handler
# ---------------------------------------------------------------------------


def handle_edit(event: Dict[str, Any]) -> None:
    """Process an afterFileEdit event: log it and optionally lint."""
    file_path = event.get("file_path", "")
    edits = event.get("edits", [])
    conversation_id = event.get("conversation_id", "")
    generation_id = event.get("generation_id", "")

    language = detect_language(file_path) if file_path else "other"

    log_event(
        {
            "event": "file_edited",
            "conversation_id": conversation_id,
            "generation_id": generation_id,
            "file_path": file_path,
            "edit_count": len(edits) if isinstance(edits, list) else 0,
            "language": language,
        }
    )

    if language == "python" and file_path:
        _run_ruff_check(file_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        data = read_stdin()
        handle_edit(data)
    except Exception:
        pass
    write_stdout({})


if __name__ == "__main__":
    main()

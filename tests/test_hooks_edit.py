"""Tests for .cursor/hooks/on_edit.py — file edit logging and diagnostics."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".cursor" / "hooks"))

from on_edit import detect_language, handle_edit

# We need to verify logging side-effects, so import _common for paths
import _common


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("foo.py", "python"),
            ("bar.ts", "typescript"),
            ("baz.tsx", "typescript"),
            ("app.js", "javascript"),
            ("comp.jsx", "javascript"),
            ("config.yaml", "yaml"),
            ("settings.yml", "yaml"),
            ("data.json", "json"),
            ("README.md", "markdown"),
            ("Makefile", "other"),
            ("", "other"),
            ("no_extension", "other"),
            ("src/deep/nested/file.py", "python"),
            (".gitignore", "other"),
        ],
        ids=[
            "python",
            "ts",
            "tsx",
            "js",
            "jsx",
            "yaml",
            "yml",
            "json",
            "markdown",
            "makefile",
            "empty",
            "no-ext",
            "nested-python",
            "dotfile",
        ],
    )
    def test_detect_language(self, path, expected):
        assert detect_language(path) == expected

    def test_case_insensitive_extension(self):
        # detect_language lowercases the suffix, so .PY matches .py
        assert detect_language("FILE.PY") == "python"
        assert detect_language("file.py") == "python"


# ---------------------------------------------------------------------------
# handle_edit
# ---------------------------------------------------------------------------


class TestHandleEdit:
    def test_valid_python_edit_logs_event(self, tmp_path, monkeypatch):
        """A Python file edit logs a file_edited event."""
        events_log = tmp_path / "events.jsonl"
        monkeypatch.setattr(_common, "EVENTS_LOG", events_log)
        monkeypatch.setattr(_common, "OMNICURSOR_DIR", tmp_path)
        monkeypatch.setattr(_common, "SESSIONS_DIR", tmp_path / "sessions")

        handle_edit(
            {
                "file_path": "src/test.py",
                "edits": [{"old_string": "a", "new_string": "b"}],
                "conversation_id": "conv-1",
                "generation_id": "gen-1",
            }
        )

        assert events_log.exists()
        lines = events_log.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["event"] == "file_edited"
        assert entry["file_path"] == "src/test.py"
        assert entry["language"] == "python"
        assert entry["edit_count"] == 1
        assert entry["conversation_id"] == "conv-1"

    def test_non_python_file_logs_without_lint(self, tmp_path, monkeypatch):
        events_log = tmp_path / "events.jsonl"
        monkeypatch.setattr(_common, "EVENTS_LOG", events_log)
        monkeypatch.setattr(_common, "OMNICURSOR_DIR", tmp_path)
        monkeypatch.setattr(_common, "SESSIONS_DIR", tmp_path / "sessions")

        handle_edit(
            {
                "file_path": "styles.css",
                "edits": [],
                "conversation_id": "conv-2",
                "generation_id": "gen-2",
            }
        )

        entry = json.loads(events_log.read_text().strip().split("\n")[-1])
        assert entry["language"] == "other"
        assert entry["edit_count"] == 0

    def test_missing_file_path_does_not_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_common, "EVENTS_LOG", tmp_path / "events.jsonl")
        monkeypatch.setattr(_common, "OMNICURSOR_DIR", tmp_path)
        monkeypatch.setattr(_common, "SESSIONS_DIR", tmp_path / "sessions")

        handle_edit({})  # no file_path key

    def test_empty_event_does_not_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_common, "EVENTS_LOG", tmp_path / "events.jsonl")
        monkeypatch.setattr(_common, "OMNICURSOR_DIR", tmp_path)
        monkeypatch.setattr(_common, "SESSIONS_DIR", tmp_path / "sessions")

        handle_edit({"file_path": "", "edits": None})

    def test_multiple_edits_counted(self, tmp_path, monkeypatch):
        events_log = tmp_path / "events.jsonl"
        monkeypatch.setattr(_common, "EVENTS_LOG", events_log)
        monkeypatch.setattr(_common, "OMNICURSOR_DIR", tmp_path)
        monkeypatch.setattr(_common, "SESSIONS_DIR", tmp_path / "sessions")

        handle_edit(
            {
                "file_path": "app.js",
                "edits": [{"old": "a", "new": "b"}, {"old": "c", "new": "d"}, {"old": "e", "new": "f"}],
                "conversation_id": "conv-3",
            }
        )

        entry = json.loads(events_log.read_text().strip().split("\n")[-1])
        assert entry["edit_count"] == 3
        assert entry["language"] == "javascript"

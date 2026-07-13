# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from omnicursor.nodes.node_cursor_file_edit_effect.models.input import FileEditInput
from omnicursor.nodes.node_cursor_file_edit_effect.models.output import FileEditOutput
from omnicursor.nodes.node_cursor_file_edit_effect.handlers.handle_file_edited import (
    handle_file_edited,
)
from omnicursor.nodes.node_cursor_file_edit_effect.node import run


class TestFileEditModels:
    def test_input_requires_file_path(self):
        with pytest.raises(Exception):
            FileEditInput()

    def test_input_edits_defaults_empty(self):
        i = FileEditInput(file_path="src/foo.py")
        assert i.edits == []

    def test_output_has_required_fields(self):
        o = FileEditOutput(
            event="file_edited",
            file_path="foo.py",
            language="python",
            edit_count=1,
            ruff_findings=0,
        )
        assert o.language == "python"


class TestHandlerFileEdited:
    def test_python_file_detected(self):
        result = handle_file_edited(FileEditInput(file_path="src/foo.py"))
        assert result.language == "python"

    def test_non_python_file_detected(self):
        result = handle_file_edited(FileEditInput(file_path="README.md"))
        assert result.language != "python"

    def test_edit_count_matches_input(self):
        edits = [{"line": 1, "content": "x = 1"}, {"line": 2, "content": "y = 2"}]
        result = handle_file_edited(FileEditInput(file_path="src/foo.py", edits=edits))
        assert result.edit_count == 2

    def test_output_is_typed(self):
        result = handle_file_edited(FileEditInput(file_path="src/foo.py"))
        assert isinstance(result, FileEditOutput)

    def test_event_name_set(self):
        result = handle_file_edited(FileEditInput(file_path="src/foo.py"))
        assert result.event == "file_edited"

    def test_ruff_findings_is_integer(self):
        result = handle_file_edited(FileEditInput(file_path="/nonexistent/path.py"))
        assert isinstance(result.ruff_findings, int)
        assert result.ruff_findings >= 0


class TestNodeRunAPI:
    def test_run_returns_output(self):
        result = run("src/foo.py")
        assert isinstance(result, FileEditOutput)

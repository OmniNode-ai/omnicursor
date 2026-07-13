# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from omnicursor.nodes.node_cursor_shell_guard_effect.models.input import ShellGuardInput
from omnicursor.nodes.node_cursor_shell_guard_effect.models.output import (
    ShellGuardOutput,
)
from omnicursor.nodes.node_cursor_shell_guard_effect.handlers.handle_shell_command import (
    handle_shell_command,
)
from omnicursor.nodes.node_cursor_shell_guard_effect.node import run


class TestShellGuardModels:
    def test_input_requires_command(self):
        with pytest.raises(Exception):
            ShellGuardInput()

    def test_input_conversation_id_defaults_empty(self):
        i = ShellGuardInput(command="ls")
        assert i.conversation_id == ""

    def test_output_permission_field(self):
        o = ShellGuardOutput(permission="allow")
        assert o.permission == "allow"
        assert o.user_message is None


class TestHandlerShellCommand:
    def test_safe_command_is_allowed(self):
        result = handle_shell_command(ShellGuardInput(command="ls -la"))
        assert result.permission == "allow"

    def test_destructive_command_is_denied(self):
        result = handle_shell_command(ShellGuardInput(command="rm -rf /"))
        assert result.permission == "deny"
        assert result.user_message is not None

    def test_rm_rf_specific_dir_is_allowed(self):
        # HARD_BLOCK only matches rm -rf targeting / or ~, not arbitrary paths
        result = handle_shell_command(ShellGuardInput(command="rm -rf /tmp/something"))
        assert result.permission == "allow"

    def test_empty_command_is_allowed(self):
        result = handle_shell_command(ShellGuardInput(command=""))
        assert result.permission == "allow"

    def test_output_is_typed(self):
        result = handle_shell_command(ShellGuardInput(command="echo hello"))
        assert isinstance(result, ShellGuardOutput)

    def test_no_verify_is_denied(self):
        result = handle_shell_command(ShellGuardInput(command="git commit --no-verify"))
        assert result.permission == "deny"


class TestNodeRunAPI:
    def test_run_safe_command(self):
        result = run("pytest tests/")
        assert isinstance(result, ShellGuardOutput)
        assert result.permission == "allow"

    def test_run_destructive_command(self):
        result = run("rm -rf /")
        assert result.permission == "deny"

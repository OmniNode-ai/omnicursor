"""A5 — secret redaction: byte-parity with the omniclaude donor + behavior.

The pattern table in ``.cursor/hooks/lib/redaction.py`` is a byte-for-byte port
of ``omniclaude/src/omniclaude/hooks/schemas.py`` (the authoritative copy that
gates OmniClaude's broadcast topics — NOT the ``secret_redactor.py`` twin).
The parity test extracts the assignment block from both files and compares
them exactly; it is skipped when the omniclaude sibling checkout is absent.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_REDACTION_PATH = _ROOT / ".cursor" / "hooks" / "lib" / "redaction.py"
_DONOR_PATH = (
    _ROOT.parent / "omniclaude" / "src" / "omniclaude" / "hooks" / "schemas.py"
)


def _load(name: str, path: Path) -> Any:
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_mod = _load("redaction", _REDACTION_PATH)


def _pattern_block(path: Path) -> str:
    """The source block from the _SECRET_PATTERNS assignment to its closing ]."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith("_SECRET_PATTERNS")
    )
    end = next(i for i, line in enumerate(lines) if i > start and line == "]")
    return "\n".join(lines[start : end + 1])


@pytest.mark.skipif(
    not _DONOR_PATH.exists(),
    reason="omniclaude sources not checked out as a sibling repo",
)
class TestByteParity:
    def test_pattern_table_is_byte_identical_to_donor(self) -> None:
        assert _pattern_block(_REDACTION_PATH) == _pattern_block(_DONOR_PATH)


class TestRedactSecrets:
    @pytest.mark.parametrize(
        ("text", "must_not_contain", "sentinel"),
        [
            (
                "key is sk-abcdef1234567890ABCDEF1234",
                "sk-abcdef1234567890ABCDEF1234",
                "sk-***REDACTED***",
            ),
            ("aws AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE", "AKIA***REDACTED***"),
            (
                "gh ghp_" + "a" * 36,
                "ghp_" + "a" * 36,
                "ghp_***REDACTED***",
            ),
            (
                "slack xoxb-123456789012-abcdefghij",
                "xoxb-123456789012-abcdefghij",
                "xox*-***REDACTED***",
            ),
            (
                "stripe sk_live_" + "a" * 24,
                "sk_live_" + "a" * 24,
                "stripe_***REDACTED***",
            ),
            (
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
                "Bearer abcdefghijklmnopqrstuvwxyz",
                "Bearer ***REDACTED***",
            ),
            (
                "postgres://user:hunter2pass@db:5432/x",
                ":hunter2pass@",
                "://user:***REDACTED***@",
            ),
            (
                "password=supersecret123",
                "supersecret123",
                "password=***REDACTED***",
            ),
        ],
    )
    def test_known_patterns_redact(
        self, text: str, must_not_contain: str, sentinel: str
    ) -> None:
        out = _mod.redact_secrets(text)
        assert must_not_contain not in out
        assert sentinel in out

    def test_benign_text_unchanged(self) -> None:
        text = "refactor the auth module and run the tests"
        assert _mod.redact_secrets(text) == text

    def test_short_password_value_not_redacted(self) -> None:
        # Donor false-positive guard: values under 8 chars stay.
        assert _mod.redact_secrets("password=true") == "password=true"


class TestSanitizePreview:
    def test_short_text_unchanged(self) -> None:
        assert _mod.sanitize_preview("fix bug") == "fix bug"

    def test_truncates_to_max_length_with_ellipsis(self) -> None:
        # Donor semantics: reserve 3 chars for "...", never exceed max_length.
        out = _mod.sanitize_preview("x" * 200)
        assert len(out) == 100
        assert out.endswith("...")

    def test_redacts_before_truncating(self) -> None:
        secret = "sk-abcdef1234567890ABCDEF1234"
        out = _mod.sanitize_preview("key {} then ".format(secret) + "y" * 200)
        assert secret not in out
        assert "***REDACTED***" in out


class TestSanitizePatternText:
    def test_collapses_newlines_and_strips_controls(self) -> None:
        out = _mod.sanitize_pattern_text("line1\n## Fake Header\r\nline2\x00\x1b")
        assert "\n" not in out and "\r" not in out
        assert "\x00" not in out and "\x1b" not in out
        assert out == "line1 ## Fake Header line2"

    def test_redacts_secrets(self) -> None:
        out = _mod.sanitize_pattern_text("use token=verysecretvalue1 here")
        assert "verysecretvalue1" not in out

    def test_caps_length(self) -> None:
        assert len(_mod.sanitize_pattern_text("z" * 1000)) <= 300

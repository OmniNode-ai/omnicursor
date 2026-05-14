"""Tests for scripts/watch_outbox.py CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "watch_outbox.py"


def test_dry_run_replays_lines(tmp_path: Path) -> None:
    sample = (
        '{"schema_version":1,"conversation_id":"abcd1234",'
        '"session_outcome":"success","matched_agent":"planning",'
        '"matched_confidence":0.9,"files_edited":0,"prompts_classified":1,"patterns_injected":0,'
        '"session_outcome_reason":"ok"}\n'
    )
    out = tmp_path / "out.jsonl"
    out.write_text(sample, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(out), "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "SESSION OUTCOME" in proc.stdout
    assert "SUCCESS" in proc.stdout
    assert "dry-run" in proc.stdout.lower() or "Replaying" in proc.stdout


def test_dry_run_missing_file_exits_nonzero() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "/nonexistent/outbox-xyz.jsonl", "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0


def test_help_includes_dry_run() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--dry-run" in proc.stdout

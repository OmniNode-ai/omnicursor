"""Exercise the distributed copy after removing its source checkout.

Socket replies below are synthetic queued ACKs, not evidence of Kafka delivery.
All state, sockets and external interpreter stubs belong to each test.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def source_tree(tmp_path):
    source = tmp_path / "source with spaces"
    source.mkdir()
    for name in (
        ".cursor-plugin",
        "rules",
        "agents",
        "skills",
        "hooks",
        "src",
        "config",
    ):
        shutil.copytree(
            ROOT / name,
            source / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
        )
    for name in (
        "mcp.json",
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "scripts/install-plugin.sh",
        "scripts/mcp-launcher.py",
        "docs/QUICKSTART.md",
    ):
        dest = source / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
    return source


def install(source, tmp_path, *flags, extra_env=None):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "PYTHONHOME", "CLAUDE_CODE_SESSION_ID"}
    }
    env.update(
        HOME=str(home),
        CURSOR_PLUGINS_LOCAL=str(tmp_path / "plugins local"),
        OMNICURSOR_DATA_DIR=str(home / ".omnicursor"),
    )
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(source / "scripts/install-plugin.sh"), *flags],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.fixture
def copied(source_tree, tmp_path):
    result = install(source_tree, tmp_path)
    assert result.returncode == 0, result.stderr
    target = tmp_path / "plugins local/omnicursor"
    shutil.rmtree(source_tree)
    assert not source_tree.exists()
    return target


def test_copy_excludes_junk_preserves_resources_and_permissions(copied):
    assert not any(p.is_symlink() for p in [copied, *copied.rglob("*")])
    assert not any(
        p.name in {"tests", ".cursor", ".git", ".github", ".venv", "__pycache__"}
        or p.suffix == ".pyc"
        for p in copied.rglob("*")
    )
    assert len(list((copied / "src/omnicursor/nodes").glob("*/contract.yaml"))) == 7
    for rel in (
        "hooks/data/seed_patterns.json",
        "hooks/config/dod_enforcement.json",
        "config/event_registry/omnicursor.yaml",
        "docs/QUICKSTART.md",
    ):
        assert (copied / rel).read_bytes() == (ROOT / rel).read_bytes()
    assert (copied / "scripts/mcp-launcher.py").stat().st_mode == (
        ROOT / "scripts/mcp-launcher.py"
    ).stat().st_mode
    assert {p.name for p in (copied / "scripts").iterdir()} == {"mcp-launcher.py"}


def test_reinstall_removes_obsolete_files(source_tree, tmp_path):
    assert install(source_tree, tmp_path).returncode == 0
    target = tmp_path / "plugins local/omnicursor"
    (target / "obsolete.py").write_text("stale")
    result = install(source_tree, tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (target / "obsolete.py").exists()


@pytest.mark.parametrize("legacy", ["root", "staging"])
def test_migrates_only_recognized_symlink(source_tree, tmp_path, legacy):
    old = source_tree if legacy == "root" else source_tree / "build/plugin"
    old.mkdir(parents=True, exist_ok=True)
    sentinel = old / "legacy-sentinel"
    sentinel.write_text("keep")
    target = tmp_path / "plugins local/omnicursor"
    target.parent.mkdir()
    target.symlink_to(old, target_is_directory=True)
    result = install(source_tree, tmp_path)
    assert result.returncode == 0, result.stderr
    assert not target.is_symlink()
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize("kind", ["directory", "symlink", "broken_symlink"])
def test_rejects_unknown_destination(source_tree, tmp_path, kind):
    target = tmp_path / "plugins local/omnicursor"
    target.parent.mkdir()
    other = tmp_path / "other"
    if kind == "directory":
        target.mkdir()
        (target / "keep").write_text("user data")
    else:
        if kind != "broken_symlink":
            other.mkdir()
        target.symlink_to(other, target_is_directory=True)
    result = install(source_tree, tmp_path)
    assert result.returncode == 1
    assert "not managed" in result.stderr
    assert (
        target.is_symlink()
        if kind != "directory"
        else (target / "keep").read_text() == "user data"
    )


@pytest.mark.parametrize(
    "entry", ["rules/linked.mdc", "scripts/mcp-launcher.py", "src"]
)
def test_rejects_source_symlinks(source_tree, tmp_path, entry):
    p = source_tree / entry
    if p.is_dir():
        p.rename(source_tree / "original-src")
        p.symlink_to(source_tree / "original-src", target_is_directory=True)
    else:
        p.unlink(missing_ok=True)
        p.symlink_to(source_tree / "README.md")
    result = install(source_tree, tmp_path)
    assert result.returncode == 1
    assert "source symlink" in result.stderr
    assert not (tmp_path / "plugins local").exists()


@pytest.mark.parametrize("flags", [("--dry-run",), ("--status",)])
def test_read_only_flags_make_no_install_writes(source_tree, tmp_path, flags):
    before = {
        p.relative_to(source_tree): p.stat().st_mtime_ns for p in source_tree.rglob("*")
    }
    result = install(source_tree, tmp_path, *flags)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "plugins local").exists()
    assert before == {
        p.relative_to(source_tree): p.stat().st_mtime_ns for p in source_tree.rglob("*")
    }


def test_invalid_payload_leaves_previous_install(source_tree, tmp_path):
    assert install(source_tree, tmp_path).returncode == 0
    target = tmp_path / "plugins local/omnicursor"
    (target / "sentinel").write_text("original")
    (source_tree / "hooks/scripts/stop.py").unlink()
    result = install(source_tree, tmp_path)
    assert result.returncode == 1
    assert "invalid hook binding" in result.stderr
    assert (target / "sentinel").read_text() == "original"
    assert not list(tmp_path.glob(".omnicursor-install-*"))


def test_failed_replacement_restores_previous_copy(source_tree, tmp_path):
    assert install(source_tree, tmp_path).returncode == 0
    target = tmp_path / "plugins local/omnicursor"
    (target / "sentinel").write_text("original")
    # Fault injection at the OS boundary in a child interpreter, with no
    # production testing switch or alternate installer implementation.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "python3"
    injection = bin_dir / "inject.py"
    wrapper.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(injection))} "$@"\n'
    )
    injection.write_text("""import os, sys
sys.argv = sys.argv[1:]
real_replace = os.replace
def fail_once(src, dst):
    if str(src).endswith('/payload'):
        raise OSError('simulated replacement failure')
    return real_replace(src, dst)
os.replace = fail_once
exec(compile(sys.stdin.read(), '<installer>', 'exec'))
""")
    wrapper.chmod(0o755)
    result = install(
        source_tree, tmp_path, extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    )
    assert result.returncode == 1
    assert "simulated replacement failure" in result.stderr
    assert (target / "sentinel").read_text() == "original"
    assert not list(tmp_path.glob(".omnicursor-install-*"))


def test_rule_links_resolve_inside_copy_from_foreign_workspace(copied, tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    assert not (foreign / "skills").exists()
    found = set()
    for rule in (copied / "rules").glob("*.mdc"):
        for rel in re.findall(r"\]\((\.\./skills/[^)]+)\)", rule.read_text()):
            skill = (rule.parent / rel).resolve()
            assert skill.is_relative_to(copied)
            assert skill.is_file()
            found.add(skill.parent.name)
    assert {
        "onex-plan-to-tickets",
        "onex-plan-review",
        "onex-recap",
        "onex-execute-plan",
        "onex-brainstorming",
        "onex-writing-plans",
        "onex-plan-ticket",
        "onex-systematic-debugging",
        "onex-pr-review",
        "onex-handoff",
    } <= found


def test_installed_hooks_without_site_packages_or_checkout(copied, tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    home = tmp_path / "runtime-home"
    home.mkdir()
    bin_dir = tmp_path / "python shim"
    bin_dir.mkdir()
    py = bin_dir / "python3"
    py.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -S "$@"\n')
    py.chmod(0o755)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("PYTHON", "OMNICURSOR_")) and k != "CLAUDE_CODE_SESSION_ID"
    }
    env.update(
        HOME=str(home),
        PATH=f"{bin_dir}:{os.environ['PATH']}",
        OMNICURSOR_PATTERN_SYNC_HTTP="0",
        INTELLIGENCE_SERVICE_URL="http://127.0.0.1:1",
        OMNICURSOR_CONTEXT_API_TIMEOUT_MS="10",
    )
    captured = []
    stop = threading.Event()
    with tempfile.TemporaryDirectory(prefix="pr5-socket-", dir="/tmp") as sock_dir:
        address = str(Path(sock_dir) / "emit.sock")
        env["OMNICURSOR_EMIT_SOCKET"] = address
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(address)
            server.listen()
            server.settimeout(0.1)

            def receive():
                while not stop.is_set():
                    try:
                        client, _ = server.accept()
                    except TimeoutError:
                        continue
                    with client:
                        with client.makefile("rb") as stream:
                            message = json.loads(stream.readline())
                        captured.append(message)
                        reply = "ok" if message.get("command") == "ping" else "queued"
                        client.sendall((json.dumps({"status": reply}) + "\n").encode())

            thread = threading.Thread(target=receive)
            thread.start()
            cid = str(uuid4())
            fake = "sk-" + "q" * 32
            payloads = {
                "sessionStart": {},
                "beforeSubmitPrompt": {
                    "prompt": f"Debug this Python error. API key {fake}"
                },
                "beforeShellExecution": {"command": "rm -rf /"},
                "afterFileEdit": {"file_path": str(foreign / "note.md")},
                "postToolUse": {
                    "tool_name": "read_file",
                    "tool_input": {"file_path": "module.py"},
                },
                "stop": {"status": "completed"},
                "sessionEnd": {"reason": "completed"},
            }
            (foreign / "note.md").write_text("unchanged")
            results = {}
            try:
                hooks = json.loads((copied / "hooks/hooks.json").read_text())["hooks"]
                for event, payload in payloads.items():
                    command = hooks[event][0]["command"].replace(
                        "${CLAUDE_PLUGIN_ROOT}", str(copied)
                    )
                    result = subprocess.run(
                        shlex.split(command),
                        input=json.dumps({"conversation_id": cid, **payload}),
                        cwd=foreign,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    assert result.returncode == 0, result.stderr
                    results[event] = json.loads(result.stdout)
            finally:
                stop.set()
                thread.join(timeout=3)
            assert results["sessionStart"]["additional_context"]
            assert results["beforeSubmitPrompt"] == {"continue": True}
            assert results["beforeShellExecution"]["permission"] == "deny"
            assert results["postToolUse"]["additional_context"]
            assert (foreign / "note.md").read_text() == "unchanged"
            state = home / ".omnicursor"
            records = [
                json.loads(line)
                for line in (state / "events.jsonl").read_text().splitlines()
            ]
            events = {row["event"] for row in records}
            assert {
                "session_started",
                "prompt_classified",
                "shell_guard",
                "file_edited",
                "tool_executed",
                "session_stopped",
                "session_ended",
            } <= events
            prompt = next(row for row in records if row["event"] == "prompt_classified")
            assert prompt["matched_agent"]
            from uuid import UUID

            UUID(prompt["correlation_id"])
            outbox = json.loads((state / "outbox.jsonl").read_text().splitlines()[-1])
            assert outbox["conversation_id"] == cid
            assert outbox["correlation_id"] == prompt["correlation_id"]
            assert (state / "learned_patterns.json").is_file()
            by_type = {
                m["event_type"]: m["payload"] for m in captured if "event_type" in m
            }
            assert by_type["session.started"]["agent_source"] == "cursor"
            assert by_type["cursor.hook.prompt"]["agent_source"] == "cursor"
            assert (
                by_type["session.outcome"]["correlation_id"] == prompt["correlation_id"]
            )
            preview = by_type["prompt.submitted"]
            assert preview["agent_source"] == "cursor"
            assert preview["correlation_id"] == prompt["correlation_id"]
            assert len(preview["prompt_preview"]) <= 100
            assert "REDACTED" in preview["prompt_preview"]
            b5 = by_type["phase.metrics"]["payload"]
            assert b5["run_id"] == cid
            assert b5["context"]["toolchain"] == "cursor"
            assert fake not in json.dumps(captured)
            assert fake not in (state / "events.jsonl").read_text()


def test_installed_fallback_redaction_and_daemon_resource_paths(copied, tmp_path):
    code = """import json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'src'))
from omnicursor import pattern_writer
assert 'redaction' not in sys.modules  # fallback is file-loaded, without hooks/lib on sys.path
assert str(root) in str(pattern_writer._redaction_path)
assert pattern_writer.redact_secrets('sk-' + 'q' * 32) != 'sk-' + 'q' * 32
sys.path.insert(0, str(root / 'hooks/lib'))
import _common, daemon_ensure
assert _common.REPO_ROOT == root
assert len(_common.load_agent_configs()) == 17
assert _common.SEED_PATTERNS_FILE.is_file()
assert daemon_ensure._REGISTRY_PATH == root / 'config/event_registry/omnicursor.yaml'
print(json.dumps(daemon_ensure._daemon_command(sys.executable)))
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", code, str(copied)],
        cwd=tmp_path,
        env={"HOME": str(tmp_path), "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    command = json.loads(result.stdout)
    assert command[command.index("--event-registry") + 1] == str(
        copied / "config/event_registry/omnicursor.yaml"
    )


@pytest.mark.parametrize("python", [None, "/nonexistent/pr5-interpreter"])
def test_installed_hook_without_daemon_still_initializes(copied, tmp_path, python):
    env = {
        "HOME": str(tmp_path),
        "PATH": os.environ["PATH"],
        "OMNICURSOR_EMIT_SOCKET": str(tmp_path / "missing.sock"),
        "INTELLIGENCE_SERVICE_URL": "http://127.0.0.1:1",
        "OMNICURSOR_CONTEXT_API_TIMEOUT_MS": "10",
    }
    if python:
        env["OMNICURSOR_DAEMON_PYTHON"] = python
    cid = str(uuid4())
    proc = subprocess.run(
        [sys.executable, "-S", str(copied / "hooks/scripts/session-start.py")],
        input=json.dumps({"conversation_id": cid}),
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["additional_context"]
    assert (tmp_path / ".omnicursor/sessions" / f"{cid}.json").is_file()
    assert not (tmp_path / ".omnicursor/emit.pid").exists()

#!/usr/bin/env bash
# Install an independent runtime copy at ~/.cursor/plugins/local/omnicursor.
# No packages or environments are installed. Only explicitly managed destinations
# (or recognized legacy links) can be replaced; user data survives --uninstall.
set -euo pipefail
OMNICURSOR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 - "$OMNICURSOR_ROOT" "$@" <<'PY'
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

SOURCE = Path(sys.argv[1]).resolve()
PARENT = Path(os.environ.get("CURSOR_PLUGINS_LOCAL", str(Path.home() / ".cursor/plugins/local"))).expanduser().absolute()
TARGET = PARENT / "omnicursor"
MARKER = ".omnicursor-managed-install"
MARKER_CONTENT = "omnicursor-copy-v1\n"
ENTRIES = (
    ".cursor-plugin/plugin.json", "rules", "agents", "skills", "hooks", "mcp.json",
    "scripts/mcp-launcher.py", "src/omnicursor", "config", "pyproject.toml",
    "README.md", "LICENSE", "CHANGELOG.md", "docs/QUICKSTART.md",
)
EXCLUDED = {
    "tests", "__tests__", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".git", ".github", ".cursor", ".venv", "venv", "node_modules", ".DS_Store",
}
HOOK_SCRIPTS = {
    "sessionStart": "session-start.py", "beforeSubmitPrompt": "user-prompt-submit.py",
    "beforeShellExecution": "shell-guard.py", "afterFileEdit": "post-edit.py",
    "postToolUse": "post-tool-use.py", "stop": "stop.py", "sessionEnd": "session-end.py",
}


def excluded(path):
    return (path.name in EXCLUDED or path.suffix in {".pyc", ".pyo", ".pem", ".key"}
            or path.name.startswith(".env") or path.name.endswith(".egg-info"))


def selected_files(path):
    # lstat before traversal: never follow a source symlink, including a selected
    # directory's ancestors (e.g. src -> another checkout).
    for ancestor in (path, *path.parents):
        if ancestor == SOURCE:
            break
        if ancestor.is_symlink():
            raise ValueError(f"refuse source symlink: {ancestor}")
    if excluded(path):
        return
    mode = path.lstat().st_mode
    if stat.S_ISREG(mode):
        yield path
    elif stat.S_ISDIR(mode):
        for child in sorted(path.iterdir()):
            yield from selected_files(child)
    else:
        raise ValueError(f"unsupported payload file: {path}")


def destination_kind():
    if TARGET.is_symlink():
        return "legacy" if TARGET.resolve() in {SOURCE, SOURCE / "build/plugin"} else "unknown"
    if not TARGET.exists():
        return "missing"
    marker = TARGET / MARKER
    if TARGET.is_dir() and marker.is_file() and not marker.is_symlink():
        if marker.read_text() == MARKER_CONTENT:
            return "managed"
    return "unknown"


def validate(root):
    manifest = json.loads((root / ".cursor-plugin/plugin.json").read_text())
    expected = {"rules": "rules", "agents": "agents", "skills": "skills",
                "hooks": "hooks/hooks.json", "mcpServers": "mcp.json"}
    if manifest.get("name") != "omnicursor" or any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("invalid plugin manifest or component paths")
    for directory, pattern, count in (("rules", "*.mdc", 14), ("agents", "*.json", 17), ("skills", "*/SKILL.md", 17)):
        if len(list((root / directory).glob(pattern))) != count:
            raise ValueError(f"incomplete payload collection: {directory} (expected {count})")
    hooks = json.loads((root / "hooks/hooks.json").read_text())["hooks"]
    if set(hooks) != set(HOOK_SCRIPTS):
        raise ValueError("expected exactly seven hook events")
    for event, script in HOOK_SCRIPTS.items():
        command = f'python3 "${{CLAUDE_PLUGIN_ROOT}}/hooks/scripts/{script}"'
        if hooks[event] != [{"command": command}] or not (root / "hooks/scripts" / script).is_file():
            raise ValueError(f"invalid hook binding: {event}")
    server = json.loads((root / "mcp.json").read_text())["mcpServers"]["omnicursor-omnimarket"]
    if server.get("command") != "python3" or server.get("args") != ["${CLAUDE_PLUGIN_ROOT}/scripts/mcp-launcher.py"]:
        raise ValueError("invalid MCP launcher registration")
    required = ("hooks/lib/_common.py", "hooks/data/seed_patterns.json", "hooks/config/dod_enforcement.json",
                "src/omnicursor/__init__.py", "src/omnicursor/mcp/omnimarket_bridge_server.py",
                "config/event_registry/omnicursor.yaml", "docs/QUICKSTART.md")
    for rel in (*required, *(entry for entry in ENTRIES if (SOURCE / entry).is_file())):
        if not (root / rel).is_file():
            raise ValueError(f"missing payload resource: {rel}")
    if len(list((root / "src/omnicursor/nodes").glob("*/contract.yaml"))) != 7:
        raise ValueError("expected seven node contracts")
    for path in root.rglob("*"):
        if path.is_symlink() or excluded(path):
            raise ValueError(f"forbidden installed artifact: {path}")


def purge_path():
    path = Path(os.environ.get("OMNICURSOR_DATA_DIR", str(Path.home() / ".omnicursor"))).expanduser().resolve()
    if path in {Path("/"), Path.home().resolve()}:
        raise ValueError(f"refuse to purge unsafe data dir: {path}")
    if path.name != ".omnicursor":
        raise ValueError(f"refuse to purge dir not named '.omnicursor': {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--uninstall", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--purge", action="store_true")
    args = parser.parse_args(sys.argv[2:])
    if args.purge and not args.uninstall:
        parser.error("--purge only applies with --uninstall")
    kind = destination_kind()
    print(f"OmniCursor plugin: {TARGET}\n  status: {kind}")
    if args.status:
        return
    if kind == "unknown":
        raise ValueError("destination is not managed by this installer; back up the manual copy outside plugins/local before installing")
    data = purge_path() if args.purge else None
    if args.uninstall:
        if kind != "missing":
            if args.dry_run:
                print(f"[dry-run] remove {TARGET} (preserve local data)")
            elif kind == "legacy":
                TARGET.unlink()  # remove only the link, never its source
            else:
                shutil.rmtree(TARGET)
        if data is not None:
            if args.dry_run:
                print(f"[dry-run] rm -rf {data}")
            elif data.is_dir():
                shutil.rmtree(data)
        return

    files = [p for entry in ENTRIES for p in selected_files(SOURCE / entry)]
    if args.dry_run:
        for entry in ENTRIES:
            print(f"[dry-run] copy {SOURCE / entry} -> {TARGET / entry}")
        return
    # Staging and rollback live outside plugins/local so Cursor cannot discover
    # half-built plugins or the old copy during replacement.
    PARENT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".omnicursor-install-", dir=PARENT.parent))
    staged, previous = work / "payload", work / "previous"
    staged.mkdir()
    preserve_rollback = False
    try:
        for source in files:
            dest = staged / source.relative_to(SOURCE)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest, follow_symlinks=False)
        # Preserve selected directory permissions as well as file modes.
        for directory in sorted((p for p in staged.rglob("*") if p.is_dir()), reverse=True):
            shutil.copystat(SOURCE / directory.relative_to(staged), directory)
        validate(staged)
        (staged / MARKER).write_text(MARKER_CONTENT)
        if destination_kind() != kind:
            raise ValueError("destination changed during staging; rerun after inspecting it")
        if kind != "missing":
            os.replace(TARGET, previous)
        try:
            os.replace(staged, TARGET)
        except BaseException:
            if previous.exists() or previous.is_symlink():
                try:
                    os.replace(previous, TARGET)
                except OSError:
                    preserve_rollback = True
                    print(f"Rollback could not restore destination; previous install preserved at {previous}", file=sys.stderr)
            raise
    finally:
        if not preserve_rollback:
            shutil.rmtree(work)
    print("Installed independent copy (no symlinks). Restart Cursor or reload the window.")
    print("For checkout development, disable the installed plugin before using the project hook shim.")


try:
    main()
except (OSError, ValueError, KeyError, TypeError) as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(1)
PY

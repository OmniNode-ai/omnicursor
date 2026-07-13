"""Structural validation for Cursor plugin manifests and install-plugin.sh."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CURSOR_PLUGIN_MANIFEST = REPO_ROOT / ".cursor-plugin" / "plugin.json"
LEGACY_MANIFEST_PATH = REPO_ROOT / "cursor-plugin.json"
INSTALL_PLUGIN_SH_PATH = REPO_ROOT / "scripts" / "install-plugin.sh"
MCP_JSON_PATH = REPO_ROOT / ".cursor" / "mcp.json"
MCP_SERVER_NAME = "omnicursor-omnimarket"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# .cursor-plugin/plugin.json (official Cursor plugin manifest)
# ---------------------------------------------------------------------------


def test_cursor_plugin_manifest_exists() -> None:
    assert CURSOR_PLUGIN_MANIFEST.exists(), ".cursor-plugin/plugin.json not found"


def test_cursor_plugin_manifest_is_valid_json() -> None:
    data = _load_json(CURSOR_PLUGIN_MANIFEST)
    assert isinstance(data, dict)


def test_cursor_plugin_manifest_required_fields() -> None:
    data = _load_json(CURSOR_PLUGIN_MANIFEST)
    for field in ("name", "displayName", "version", "description"):
        assert field in data, f".cursor-plugin/plugin.json missing field: {field}"


def test_cursor_plugin_manifest_name() -> None:
    data = _load_json(CURSOR_PLUGIN_MANIFEST)
    assert data["name"] == "omnicursor"


def test_cursor_plugin_manifest_component_paths() -> None:
    data = _load_json(CURSOR_PLUGIN_MANIFEST)
    for key in ("rules", "agents", "skills", "hooks"):
        assert key in data, f"plugin.json missing component path: {key}"
        path = REPO_ROOT / data[key]
        assert path.exists(), f"component '{key}' path {path} does not exist"


def test_cursor_plugin_manifest_hooks_is_hooks_json() -> None:
    data = _load_json(CURSOR_PLUGIN_MANIFEST)
    assert data["hooks"].endswith("hooks.json")


def test_cursor_plugin_manifest_version_format() -> None:
    data = _load_json(CURSOR_PLUGIN_MANIFEST)
    parts = data["version"].split(".")
    assert len(parts) == 3, "version must be semver (X.Y.Z)"
    for part in parts:
        assert part.isdigit(), f"version part '{part}' is not an integer"


# ---------------------------------------------------------------------------
# Single canonical manifest (A10.2): the homegrown root cursor-plugin.json is
# gone and the official manifest carries only official Cursor plugin fields.
# ---------------------------------------------------------------------------

# Official `cursor/plugins` manifest fields plus documented marketplace fields
# (CURSOR_PLUGIN_RESEARCH_2026-06-18.md §Manifest). The strict AJV schema may
# reject unknown top-level keys, so non-official keys (`requires`, `install`,
# `execution`, `surfaces`, `manifest`) must never reappear: their facts live in
# README (cursor floor) and pyproject.toml (python floor) instead.
# Single source of truth: the CI gate's allowlist (scripts/ci isn't a package,
# so load it by path).
_spec = importlib.util.spec_from_file_location(
    "_check_manifest_gate", REPO_ROOT / "scripts" / "ci" / "check_manifest.py"
)
assert _spec is not None and _spec.loader is not None
_check_manifest_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_check_manifest_gate)
OFFICIAL_MANIFEST_FIELDS = _check_manifest_gate.OFFICIAL_MANIFEST_FIELDS


def test_legacy_manifest_removed() -> None:
    assert not LEGACY_MANIFEST_PATH.exists(), (
        "cursor-plugin.json must not exist: .cursor-plugin/plugin.json is the "
        "single canonical manifest (A10.2)"
    )


def test_official_manifest_uses_only_official_fields() -> None:
    data = _load_json(CURSOR_PLUGIN_MANIFEST)
    unknown = set(data) - OFFICIAL_MANIFEST_FIELDS
    assert not unknown, (
        f"non-official manifest keys {sorted(unknown)} risk failing the strict "
        "cursor/plugins schema; keep such facts in README/pyproject instead"
    )


# ---------------------------------------------------------------------------
# .cursor/mcp.json (A10.3): shipped, tracked, and naming-consistent with the
# FastMCP bridge server and the skill that depends on it by name.
# ---------------------------------------------------------------------------


def test_mcp_json_exists() -> None:
    assert MCP_JSON_PATH.exists(), ".cursor/mcp.json not found (A10.3 MCP wiring)"


def test_mcp_json_has_mcp_servers_wrapper() -> None:
    data = _load_json(MCP_JSON_PATH)
    assert "mcpServers" in data, ".cursor/mcp.json must use the mcpServers wrapper"
    assert isinstance(data["mcpServers"], dict)


def test_mcp_json_registers_bridge_server() -> None:
    servers = _load_json(MCP_JSON_PATH)["mcpServers"]
    assert MCP_SERVER_NAME in servers, (
        f".cursor/mcp.json must register '{MCP_SERVER_NAME}' — the exact name "
        "skills/execute-plan.md depends on"
    )
    entry = servers[MCP_SERVER_NAME]
    assert "command" in entry and "args" in entry


def test_mcp_server_name_matches_bridge_source() -> None:
    source = (REPO_ROOT / "src/omnicursor/mcp/omnimarket_bridge_server.py").read_text()
    assert f'FastMCP("{MCP_SERVER_NAME}")' in source


def test_mcp_server_name_matches_skill_consumers() -> None:
    for skill in (
        "skills/execute-plan.md",
        ".cursor/skills/onex-execute-plan/SKILL.md",
    ):
        assert MCP_SERVER_NAME in (REPO_ROOT / skill).read_text(), (
            f"{skill} no longer references '{MCP_SERVER_NAME}'"
        )


def test_mcp_json_is_not_gitignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", ".cursor/mcp.json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        ".cursor/mcp.json is gitignored — it would silently never ship (A10.3)"
    )


def test_manifest_references_mcp_json() -> None:
    data = _load_json(CURSOR_PLUGIN_MANIFEST)
    assert data.get("mcpServers") == ".cursor/mcp.json"


# ---------------------------------------------------------------------------
# scripts/install-plugin.sh
# ---------------------------------------------------------------------------


def test_install_plugin_sh_exists() -> None:
    assert INSTALL_PLUGIN_SH_PATH.exists(), "scripts/install-plugin.sh not found"


def test_install_plugin_sh_is_executable() -> None:
    assert os.access(INSTALL_PLUGIN_SH_PATH, os.X_OK), (
        "scripts/install-plugin.sh is not executable"
    )


def test_install_plugin_sh_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_PLUGIN_SH_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"install-plugin.sh has syntax errors:\n{result.stderr}"
    )


def test_install_plugin_sh_has_shebang() -> None:
    first_line = INSTALL_PLUGIN_SH_PATH.read_text().splitlines()[0]
    assert first_line.startswith("#!"), "install-plugin.sh missing shebang line"


def test_install_plugin_sh_targets_cursor_plugins_local() -> None:
    content = INSTALL_PLUGIN_SH_PATH.read_text()
    assert "plugins/local" in content
    assert "omnicursor" in content


# ---------------------------------------------------------------------------
# Curated install payload (A10.4) + uninstall hygiene (A10.5).
# These drive the real script against sandbox CURSOR_PLUGINS_LOCAL /
# OMNICURSOR_DATA_DIR dirs; the repo-side staging dir (build/plugin) is
# gitignored and rebuilt on every install.
# ---------------------------------------------------------------------------

DEV_JUNK = ("tests", ".git", ".github", "compose.yaml", "docker", "eval", ".venv")


def _run_installer(*flags: str, plugins_dir: Path, data_dir: Path | None = None):
    env = dict(os.environ, CURSOR_PLUGINS_LOCAL=str(plugins_dir))
    if data_dir is not None:
        env["OMNICURSOR_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        ["bash", str(INSTALL_PLUGIN_SH_PATH), *flags],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )


def test_install_dry_run_stages_only_curated_payload(tmp_path: Path) -> None:
    result = _run_installer("--dry-run", plugins_dir=tmp_path / "plugins")
    assert result.returncode == 0, result.stderr
    staged = [line for line in result.stdout.splitlines() if "ln -s" in line]
    assert staged, "dry-run must print the planned payload links"
    for junk in DEV_JUNK:
        assert not any(
            f"/{junk} " in line or line.endswith(f"/{junk}") for line in staged
        ), f"dev junk '{junk}' appears in the staged payload"
    joined = "\n".join(staged)
    assert "src/omnicursor" in joined
    assert "config" in joined


def test_install_payload_and_uninstall_lifecycle(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    data = tmp_path / ".omnicursor"
    data.mkdir()
    (data / "learned_patterns.json").write_text("{}")

    result = _run_installer(plugins_dir=plugins)
    assert result.returncode == 0, result.stderr
    installed = plugins / "omnicursor"
    assert installed.is_symlink()

    for junk in DEV_JUNK:
        assert not (installed / junk).exists(), (
            f"installed payload ships dev junk: {junk}"
        )
    assert (installed / ".cursor" / "hooks.json").exists()
    assert (installed / ".cursor" / "mcp.json").exists()
    assert (installed / "src" / "omnicursor" / "__init__.py").exists()
    assert (installed / "config" / "event_registry" / "omnicursor.yaml").exists(), (
        "daemon registry must ship with the payload (risk P6)"
    )

    # Plain uninstall removes the symlink but preserves local data.
    result = _run_installer("--uninstall", plugins_dir=plugins, data_dir=data)
    assert result.returncode == 0, result.stderr
    assert not installed.exists()
    assert (data / "learned_patterns.json").exists(), "plain --uninstall must keep data"


def test_uninstall_purge_is_opt_in_and_guarded(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    data = tmp_path / ".omnicursor"
    data.mkdir()
    (data / "outbox.jsonl").write_text("")

    assert _run_installer(plugins_dir=plugins).returncode == 0

    # --purge without --uninstall is rejected.
    result = _run_installer("--purge", plugins_dir=plugins, data_dir=data)
    assert result.returncode != 0

    # Dry-run shows the purge without executing it. (The script resolves
    # symlinks before printing, so assert on the basename, not the raw path.)
    result = _run_installer(
        "--uninstall", "--purge", "--dry-run", plugins_dir=plugins, data_dir=data
    )
    assert result.returncode == 0, result.stderr
    assert "rm -rf" in result.stdout and ".omnicursor" in result.stdout
    assert data.exists()

    # Real purge removes the data dir.
    result = _run_installer(
        "--uninstall", "--purge", plugins_dir=plugins, data_dir=data
    )
    assert result.returncode == 0, result.stderr
    assert not data.exists()


def test_uninstall_purge_refuses_unsafe_data_dir(tmp_path: Path) -> None:
    result = _run_installer(
        "--uninstall", "--purge", plugins_dir=tmp_path / "plugins", data_dir=Path("/")
    )
    assert result.returncode != 0
    assert "refuse to purge" in result.stdout + result.stderr


def test_uninstall_purge_refuses_dir_not_named_omnicursor(tmp_path: Path) -> None:
    # The hooks only ever write ~/.omnicursor; a typo'd OMNICURSOR_DATA_DIR
    # pointing anywhere else must be refused, not rm -rf'd.
    data = tmp_path / "important-stuff"
    data.mkdir()
    (data / "keep.me").write_text("")
    result = _run_installer(
        "--uninstall", "--purge", plugins_dir=tmp_path / "plugins", data_dir=data
    )
    assert result.returncode != 0
    assert "not named '.omnicursor'" in result.stdout + result.stderr
    assert (data / "keep.me").exists()

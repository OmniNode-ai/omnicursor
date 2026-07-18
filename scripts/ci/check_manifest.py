#!/usr/bin/env python3
"""CI gate (A10.7): plugin manifest + MCP wiring validation.

Validates the single canonical manifest (A10.2) against the **pinned official
`cursor/plugins` schema** (`schemas/cursor-plugin.schema.json` — provenance in
`schemas/README.md`), plus the project invariants the schema cannot express:
component paths exist, semver version, CHANGELOG/version sync (A10.1), and
the shipped MCP registration (A10.3).

Exit 0 = clean; exit 1 = findings printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MCP_SERVER_NAME = "omnicursor-omnimarket"
SCHEMA_RELPATH = "schemas/cursor-plugin.schema.json"


def _validate_against_official_schema(manifest: dict, findings: list[str]) -> None:
    """Official-schema validation (strict: additionalProperties=false, name
    pattern/required). Replaces the former handwritten field allowlist.

    The pinned schema ships with this gate (script-relative, not --root
    relative), so sandbox fixtures validate against the same schema."""
    try:
        import jsonschema
    except ImportError:
        findings.append(
            f"{SCHEMA_RELPATH}: jsonschema not installed — the official-schema "
            "gate cannot run (pip install jsonschema)"
        )
        return
    schema_path = Path(__file__).resolve().parents[2] / SCHEMA_RELPATH
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        findings.append(f"{schema_path}: unreadable pinned schema ({exc})")
        return
    validator = jsonschema.Draft7Validator(schema)
    for error in sorted(validator.iter_errors(manifest), key=str):
        where = "/".join(str(p) for p in error.absolute_path) or "<root>"
        findings.append(f"plugin.json vs official schema: {where}: {error.message}")


def _load_json(path: Path, findings: list[str]) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        findings.append(f"{path}: missing")
        return None
    except json.JSONDecodeError as exc:
        findings.append(f"{path}: invalid JSON ({exc})")
        return None
    if not isinstance(data, dict):
        findings.append(f"{path}: top level must be a JSON object")
        return None
    return data


def check(root: Path) -> list[str]:
    findings: list[str] = []
    manifest_path = root / ".cursor-plugin" / "plugin.json"
    mcp_path = root / ".cursor" / "mcp.json"

    # Single canonical manifest (A10.2).
    if (root / "cursor-plugin.json").exists():
        findings.append(
            "cursor-plugin.json: legacy root manifest must not exist "
            "(.cursor-plugin/plugin.json is the single canonical manifest)"
        )

    manifest = _load_json(manifest_path, findings)
    if manifest is not None:
        # Official schema: required name (+ pattern), field types, and the
        # strict additionalProperties=false key check.
        _validate_against_official_schema(manifest, findings)
        # Project policy on top of the schema (which requires only 'name').
        for field in ("displayName", "version", "description"):
            if not manifest.get(field):
                findings.append(f"{manifest_path}: missing required field '{field}'")
        version = str(manifest.get("version", ""))
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            findings.append(f"{manifest_path}: version '{version}' is not semver X.Y.Z")
        for key in ("rules", "agents", "skills", "hooks"):
            rel = manifest.get(key)
            if not rel:
                findings.append(f"{manifest_path}: missing component path '{key}'")
            elif not isinstance(rel, str):
                findings.append(
                    f"{manifest_path}: component '{key}' must be a string path"
                )
            elif not (root / rel).exists():
                findings.append(
                    f"{manifest_path}: component '{key}' path {rel} does not exist"
                )
        if manifest.get("mcpServers") != ".cursor/mcp.json":
            findings.append(
                f"{manifest_path}: 'mcpServers' must reference .cursor/mcp.json (A10.3)"
            )

        # CHANGELOG top versioned entry matches the manifest version (A10.1).
        changelog = root / "CHANGELOG.md"
        if not changelog.exists():
            findings.append("CHANGELOG.md: missing (A10.1)")
        else:
            versions = re.findall(
                r"^## \[(\d+\.\d+\.\d+)\]", changelog.read_text(), re.M
            )
            if not versions:
                findings.append("CHANGELOG.md: no versioned '## [X.Y.Z]' entry found")
            elif version and versions[0] != version:
                findings.append(
                    f"CHANGELOG.md: top versioned entry {versions[0]} != manifest {version}"
                )

    # MCP wiring (A10.3).
    mcp = _load_json(mcp_path, findings)
    if mcp is not None:
        servers = mcp.get("mcpServers")
        if not isinstance(servers, dict):
            findings.append(f"{mcp_path}: must have a top-level 'mcpServers' object")
        else:
            entry = servers.get(MCP_SERVER_NAME)
            if not isinstance(entry, dict):
                findings.append(f"{mcp_path}: must register '{MCP_SERVER_NAME}'")
            elif not ("command" in entry and "args" in entry):
                findings.append(f"{mcp_path}: '{MCP_SERVER_NAME}' needs command+args")

        bridge = root / "src/omnicursor/mcp/omnimarket_bridge_server.py"
        if (
            bridge.exists()
            and f'FastMCP("{MCP_SERVER_NAME}")' not in bridge.read_text()
        ):
            findings.append(f"{bridge}: FastMCP server name != '{MCP_SERVER_NAME}'")

        ignored = subprocess.run(
            ["git", "check-ignore", ".cursor/mcp.json"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if ignored.returncode == 0:
            findings.append(
                ".cursor/mcp.json: gitignored — it would silently never ship (A10.3)"
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repo root (default: two levels above this script)",
    )
    args = parser.parse_args()

    findings = check(args.root.resolve())
    for finding in findings:
        print(f"MANIFEST GATE: {finding}")
    if findings:
        return 1
    print("manifest gate: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

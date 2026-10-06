"""Tests for the A10.7 CI gate scripts (scripts/ci/*.py).

Two angles per gate: it passes on the real tree (CI green post-Phase-1/2),
and it catches a synthetic reproduction of the historical defect it exists
to prevent (the A9 frontmatter bugs, the PR-#4 topic literals, a platform
import in a hook, a non-official manifest key).
"""

from __future__ import annotations

import json
import shutil

import pytest
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATES_DIR = REPO_ROOT / "scripts" / "ci"

MANIFEST_GATE = GATES_DIR / "check_manifest.py"
FRONTMATTER_GATE = GATES_DIR / "check_frontmatter.py"
TOPIC_GATE = GATES_DIR / "check_topic_literals.py"
STDLIB_GATE = GATES_DIR / "check_hook_stdlib_only.py"

ALL_GATES = (MANIFEST_GATE, FRONTMATTER_GATE, TOPIC_GATE, STDLIB_GATE)


def _run(script: Path, root: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(script)]
    if root is not None:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


# ---------------------------------------------------------------------------
# Green on the real tree
# ---------------------------------------------------------------------------


def test_all_gates_pass_on_current_tree() -> None:
    for script in ALL_GATES:
        result = _run(script)
        assert result.returncode == 0, (
            f"{script.name} failed:\n{result.stdout}{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Frontmatter gate — the A9 defect classes
# ---------------------------------------------------------------------------


def _frontmatter_fixture(root: Path) -> None:
    for name in ("skills", "agents"):
        shutil.copytree(REPO_ROOT / name, root / name)
    compliance = root / "src/omnicursor/compliance.py"
    compliance.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "src/omnicursor/compliance.py", compliance)
    assert _run(FRONTMATTER_GATE, root).returncode == 0


def test_frontmatter_gate_flags_degenerate_description(tmp_path: Path) -> None:
    _frontmatter_fixture(tmp_path)
    broken = tmp_path / "skills/onex-hostile-reviewer/SKILL.md"
    broken.write_text("---\nname: onex-hostile-reviewer\ndescription: '---'\n---\n")
    result = _run(FRONTMATTER_GATE, tmp_path)
    assert result.returncode == 1
    assert "degenerate 'description'" in result.stdout
    assert "expected exactly" not in result.stdout


def test_frontmatter_gate_flags_truncated_description(tmp_path: Path) -> None:
    _frontmatter_fixture(tmp_path)
    broken = tmp_path / "skills/onex-execute-plan/SKILL.md"
    broken.write_text(
        "---\nname: onex-execute-plan\ndescription: Loads a plan document, reviews it adversarially,\n---\n"
    )
    result = _run(FRONTMATTER_GATE, tmp_path)
    assert result.returncode == 1
    assert "truncated mid-sentence" in result.stdout
    assert "expected exactly" not in result.stdout


def test_frontmatter_gate_flags_name_mismatch(tmp_path: Path) -> None:
    _frontmatter_fixture(tmp_path)
    path = tmp_path / "skills/onex-recap/SKILL.md"
    path.write_text(path.read_text().replace('name: "onex-recap"', "name: wrong"))
    result = _run(FRONTMATTER_GATE, tmp_path)
    assert result.returncode == 1
    assert "name must match directory" in result.stdout


def test_frontmatter_gate_reports_missing_skill_document(tmp_path: Path) -> None:
    _frontmatter_fixture(tmp_path)
    (tmp_path / "skills/onex-recap/SKILL.md").unlink()
    result = _run(FRONTMATTER_GATE, tmp_path)
    assert result.returncode == 1
    assert "missing SKILL.md" in result.stdout
    assert "Traceback" not in result.stderr


def test_frontmatter_gate_flags_duplicate_agent_category(tmp_path: Path) -> None:
    _frontmatter_fixture(tmp_path)
    first = json.loads((tmp_path / "agents/pr-review.json").read_text())
    path = tmp_path / "agents/address-pr-comments.json"
    second = json.loads(path.read_text())
    second["category"] = first["category"]
    path.write_text(json.dumps(second))
    result = _run(FRONTMATTER_GATE, tmp_path)
    assert result.returncode == 1
    assert "duplicate category" in result.stdout


@pytest.mark.parametrize("collection", ["skills", "agents"])
@pytest.mark.parametrize("missing", [True, False], ids=["absent", "empty"])
def test_frontmatter_requires_collections(
    tmp_path: Path, collection: str, missing: bool
) -> None:
    _frontmatter_fixture(tmp_path)
    shutil.rmtree(tmp_path / collection)
    if not missing:
        (tmp_path / collection).mkdir()
    result = _run(FRONTMATTER_GATE, tmp_path)
    assert result.returncode == 1
    assert f"{collection}: " in result.stdout
    assert (
        "missing directory" in result.stdout
        if missing
        else "empty collection" in result.stdout
    )


@pytest.mark.parametrize(
    "mutation", ["missing", "unexpected", "registry_missing", "both_missing"]
)
def test_compliance_requires_exact_collection(tmp_path: Path, mutation: str) -> None:
    _frontmatter_fixture(tmp_path)
    if mutation in {"missing", "both_missing"}:
        shutil.rmtree(tmp_path / "skills/onex-recap")
    if mutation == "unexpected":
        shutil.copytree(tmp_path / "skills/onex-recap", tmp_path / "skills/onex-extra")
    if mutation in {"registry_missing", "both_missing"}:
        path = tmp_path / "src/omnicursor/compliance.py"
        path.write_text(path.read_text().replace('"onex-recap":', '"onex-unexpected":'))
    result = subprocess.run(
        [
            sys.executable,
            str(FRONTMATTER_GATE),
            "--root",
            str(tmp_path),
            "--compliance-only",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "17 IDs" in result.stdout or "IDs differ" in result.stdout


# ---------------------------------------------------------------------------
# Topic-literal gate — the PR-#4 defect class
# ---------------------------------------------------------------------------


def _hook_fixture(root: Path, name: str, source: str) -> Path:
    path = root / "hooks" / "scripts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return path


def test_topic_gate_flags_hardcoded_literal(tmp_path: Path) -> None:
    (tmp_path / "hooks" / "lib").mkdir(parents=True)
    _hook_fixture(
        tmp_path,
        "bad-hook.py",
        'def main():\n    send_event("onex.evt.omnicursor.tool-executed.v1", {})\n',
    )
    result = _run(TOPIC_GATE, root=tmp_path)
    assert result.returncode == 1
    assert "hardcoded topic literal" in result.stdout


def test_topic_gate_allows_docstring_reference_and_semantic_keys(
    tmp_path: Path,
) -> None:
    (tmp_path / "hooks" / "lib").mkdir(parents=True)
    _hook_fixture(
        tmp_path,
        "good-hook.py",
        '"""Fans out to the restricted onex.cmd.omniintelligence topic via the registry."""\n'
        'def main():\n    send_event("cursor.hook.prompt", {})\n',
    )
    result = _run(TOPIC_GATE, root=tmp_path)
    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------------------
# Stdlib-only gate — the transport ruling
# ---------------------------------------------------------------------------


def test_stdlib_gate_flags_platform_import(tmp_path: Path) -> None:
    (tmp_path / "hooks" / "lib" / "_common.py").parent.mkdir(parents=True)
    (tmp_path / "hooks" / "lib" / "_common.py").write_text("X = 1\n")
    _hook_fixture(
        tmp_path, "bad-import.py", "import pydantic\nfrom omnimarket import x\n"
    )
    result = _run(STDLIB_GATE, root=tmp_path)
    assert result.returncode == 1
    assert "non-stdlib import 'pydantic'" in result.stdout
    assert "non-stdlib import 'omnimarket'" in result.stdout


def test_stdlib_gate_allows_stdlib_lib_and_first_party(tmp_path: Path) -> None:
    (tmp_path / "hooks" / "lib" / "_common.py").parent.mkdir(parents=True)
    (tmp_path / "hooks" / "lib" / "_common.py").write_text("X = 1\n")
    _hook_fixture(
        tmp_path,
        "good-import.py",
        "import json\nimport sys\nfrom _common import X\nfrom omnicursor import scoring\n",
    )
    result = _run(STDLIB_GATE, root=tmp_path)
    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------------------
# Manifest gate — the A10.2 invariants
# ---------------------------------------------------------------------------


def test_manifest_gate_flags_legacy_manifest_and_unknown_keys(tmp_path: Path) -> None:
    (tmp_path / "cursor-plugin.json").write_text("{}")
    plugin = tmp_path / ".cursor-plugin" / "plugin.json"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        json.dumps(
            {
                "name": "omnicursor",
                "displayName": "OmniCursor",
                "version": "0.1.0",
                "description": "fixture",
                "requires": {"cursor": ">=0.40.0"},
            }
        )
    )
    result = _run(MANIFEST_GATE, root=tmp_path)
    assert result.returncode == 1
    assert "legacy root manifest" in result.stdout
    # Unknown keys are caught by the pinned official schema now
    # (additionalProperties=false), not a handwritten allowlist.
    assert "official schema" in result.stdout and "'requires'" in result.stdout


@pytest.mark.parametrize("gate", [TOPIC_GATE, STDLIB_GATE])
@pytest.mark.parametrize("missing", [True, False], ids=["absent", "empty"])
def test_hook_gates_require_python_tree(
    tmp_path: Path, gate: Path, missing: bool
) -> None:
    if not missing:
        (tmp_path / "hooks").mkdir()
    result = _run(gate, tmp_path)
    assert result.returncode == 1
    assert "hooks" in result.stdout


@pytest.mark.parametrize("missing", [True, False], ids=["absent", "empty"])
def test_stdlib_gate_requires_helpers(tmp_path: Path, missing: bool) -> None:
    _hook_fixture(tmp_path, "good.py", "import json\n")
    if not missing:
        (tmp_path / "hooks/lib").mkdir()
    result = _run(STDLIB_GATE, tmp_path)
    assert result.returncode == 1
    assert "hooks/lib" in result.stdout


@pytest.mark.parametrize(
    "resource",
    [
        "mcp.json",
        "scripts/mcp-launcher.py",
        "hooks/data/seed_patterns.json",
        "config/event_registry/omnicursor.yaml",
    ],
)
def test_manifest_requires_runtime_resources(tmp_path: Path, resource: str) -> None:
    for name in (
        ".cursor-plugin",
        "rules",
        "agents",
        "skills",
        "hooks",
        "src",
        "config",
        "docs",
    ):
        shutil.copytree(
            REPO_ROOT / name,
            tmp_path / name,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (tmp_path / "scripts").mkdir()
    for name in (
        "mcp.json",
        "scripts/mcp-launcher.py",
        "CHANGELOG.md",
        "pyproject.toml",
    ):
        shutil.copy2(REPO_ROOT / name, tmp_path / name)
    assert _run(MANIFEST_GATE, tmp_path).returncode == 0
    (tmp_path / resource).unlink()
    result = _run(MANIFEST_GATE, tmp_path)
    assert result.returncode == 1
    assert resource in result.stdout

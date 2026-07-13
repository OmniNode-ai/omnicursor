"""Tests for the A10.7 CI gate scripts (scripts/ci/*.py).

Two angles per gate: it passes on the real tree (CI green post-Phase-1/2),
and it catches a synthetic reproduction of the historical defect it exists
to prevent (the A9 frontmatter bugs, the PR-#4 topic literals, a platform
import in a hook, a non-official manifest key).
"""

from __future__ import annotations

import json
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


def _skill_fixture(root: Path, slug: str, description: str) -> None:
    body = (
        f"---\nname: onex-{slug}\ndescription: >-\n  {description}\n---\n\n# {slug}\n"
    )
    canonical = root / "skills" / f"{slug}.md"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text(body)
    mirror = root / ".cursor" / "skills" / f"onex-{slug}" / "SKILL.md"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(body)


def _agent_fixture(root: Path, name: str, category: str) -> None:
    path = root / ".cursor" / "agents" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": name,
                "description": f"A perfectly reasonable description for {name}.",
                "category": category,
                "activation_patterns": {
                    "explicit_triggers": [name],
                    "context_triggers": [],
                    "activation_keywords": [name],
                },
                "instructions": "Do the thing.",
                "recommended_skill": f"onex-{name}",
            }
        )
    )


def test_frontmatter_gate_flags_degenerate_description(tmp_path: Path) -> None:
    # The hostile-reviewer shape: folded description whose value is '---'.
    _skill_fixture(tmp_path, "good", "Adversarial review that iterates to convergence.")
    broken = tmp_path / "skills" / "broken.md"
    broken.write_text("---\nname: onex-broken\ndescription: '---'\n---\n\n# broken\n")
    mirror = tmp_path / ".cursor" / "skills" / "onex-broken" / "SKILL.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(broken.read_text())

    result = _run(FRONTMATTER_GATE, root=tmp_path)
    assert result.returncode == 1
    assert "degenerate 'description'" in result.stdout


def test_frontmatter_gate_flags_truncated_description(tmp_path: Path) -> None:
    # The execute-plan shape: description cut off mid-sentence.
    _skill_fixture(tmp_path, "cut", "Loads a plan document, reviews it adversarially,")
    result = _run(FRONTMATTER_GATE, root=tmp_path)
    assert result.returncode == 1
    assert "truncated mid-sentence" in result.stdout


def test_frontmatter_gate_flags_dual_location_drift(tmp_path: Path) -> None:
    _skill_fixture(
        tmp_path, "drift", "A long enough description for the fixture skill."
    )
    mirror = tmp_path / ".cursor" / "skills" / "onex-drift" / "SKILL.md"
    mirror.write_text(mirror.read_text() + "\nmirror-only edit\n")
    result = _run(FRONTMATTER_GATE, root=tmp_path)
    assert result.returncode == 1
    assert "dual-location parity" in result.stdout


def test_frontmatter_gate_flags_duplicate_agent_category(tmp_path: Path) -> None:
    # The pr-review/address-pr-comments shape: two agents, one category.
    _skill_fixture(tmp_path, "ok", "A long enough description for the fixture skill.")
    _agent_fixture(tmp_path, "pr-review", "review")
    _agent_fixture(tmp_path, "address-pr-comments", "review")
    result = _run(FRONTMATTER_GATE, root=tmp_path)
    assert result.returncode == 1
    assert "duplicate category 'review'" in result.stdout


# ---------------------------------------------------------------------------
# Topic-literal gate — the PR-#4 defect class
# ---------------------------------------------------------------------------


def _hook_fixture(root: Path, name: str, source: str) -> Path:
    path = root / ".cursor" / "hooks" / "scripts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return path


def test_topic_gate_flags_hardcoded_literal(tmp_path: Path) -> None:
    (tmp_path / ".cursor" / "hooks" / "lib").mkdir(parents=True)
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
    (tmp_path / ".cursor" / "hooks" / "lib").mkdir(parents=True)
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
    (tmp_path / ".cursor" / "hooks" / "lib" / "_common.py").parent.mkdir(parents=True)
    (tmp_path / ".cursor" / "hooks" / "lib" / "_common.py").write_text("X = 1\n")
    _hook_fixture(
        tmp_path, "bad-import.py", "import pydantic\nfrom omnimarket import x\n"
    )
    result = _run(STDLIB_GATE, root=tmp_path)
    assert result.returncode == 1
    assert "non-stdlib import 'pydantic'" in result.stdout
    assert "non-stdlib import 'omnimarket'" in result.stdout


def test_stdlib_gate_allows_stdlib_lib_and_first_party(tmp_path: Path) -> None:
    (tmp_path / ".cursor" / "hooks" / "lib" / "_common.py").parent.mkdir(parents=True)
    (tmp_path / ".cursor" / "hooks" / "lib" / "_common.py").write_text("X = 1\n")
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
    assert "non-official keys" in result.stdout and "requires" in result.stdout

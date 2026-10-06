#!/usr/bin/env python3
"""CI gate (A10.7): skill frontmatter + agent config validation.

Catches the exact defect classes Phase-1 A9 fixed so they cannot regress:
  - broken/degenerate skill descriptions (hostile-reviewer's folded value was
    literally ``---``; execute-plan's was truncated mid-sentence),
  - absent, empty, incomplete or misnamed skill collections,
  - agent configs missing required fields,
  - duplicate agent categories (the pr-review/address-pr-comments collision;
    hard uniqueness encodes the A9 `review-response` disambiguation — drop to
    an allowlist if the team later rules categories may repeat).

Exit 0 = clean; exit 1 = findings printed to stdout.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

import yaml

EXPECTED_SKILL_IDS = frozenset(
    {
        "onex-brainstorming",
        "onex-defense-in-depth",
        "onex-docs-reality-sync",
        "onex-execute-plan",
        "onex-handoff",
        "onex-hostile-reviewer",
        "onex-insights-to-plan",
        "onex-merge-planner",
        "onex-plan-review",
        "onex-plan-ticket",
        "onex-plan-to-tickets",
        "onex-pr-polish",
        "onex-pr-review",
        "onex-recap",
        "onex-systematic-debugging",
        "onex-using-git-worktrees",
        "onex-writing-plans",
    }
)

MIN_DESCRIPTION_LEN = 20
_FM_DELIMITER = re.compile(r"^---\s*$", re.MULTILINE)
AGENT_REQUIRED_FIELDS = (
    "name",
    "description",
    "category",
    "activation_patterns",
    "instructions",
)
ACTIVATION_REQUIRED_KEYS = (
    "explicit_triggers",
    "context_triggers",
    "activation_keywords",
)


def _frontmatter(path: Path, findings: list[str]) -> dict | None:
    text = path.read_text(encoding="utf-8")
    # Frontmatter delimiters are line-anchored `---` (an inline '---' value
    # must not terminate the block).
    delimiters = list(_FM_DELIMITER.finditer(text))
    if not delimiters or delimiters[0].start() != 0:
        findings.append(f"{path}: missing YAML frontmatter block")
        return None
    if len(delimiters) < 2:
        findings.append(f"{path}: unterminated YAML frontmatter block")
        return None
    block = text[delimiters[0].end() : delimiters[1].start()]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        findings.append(f"{path}: frontmatter is not valid YAML ({exc})")
        return None
    if not isinstance(data, dict):
        findings.append(f"{path}: frontmatter is not a YAML mapping")
        return None
    return data


def _check_description(path: Path, data: dict, findings: list[str]) -> None:
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        findings.append(f"{path}: missing/empty 'description'")
        return
    desc = description.strip()
    if set(desc) <= {"-"}:
        findings.append(f"{path}: degenerate 'description' ({desc!r})")
    elif len(desc) < MIN_DESCRIPTION_LEN:
        findings.append(f"{path}: 'description' too short to be meaningful ({desc!r})")
    elif desc.endswith((",", ";")):
        findings.append(
            f"{path}: 'description' looks truncated mid-sentence ({desc[-40:]!r})"
        )


def check_skills(root: Path) -> list[str]:
    findings: list[str] = []
    directory = root / "skills"
    if not directory.is_dir():
        return ["skills: missing directory"]
    paths = sorted(directory.glob("*/SKILL.md"))
    if not paths:
        findings.append("skills: empty collection (no SKILL.md files)")
    for child in sorted(directory.iterdir()):
        if child.is_dir() and not (child / "SKILL.md").is_file():
            findings.append(f"{child}: missing SKILL.md")
        elif child.is_file() and child.name != "README.md":
            findings.append(f"{child}: unexpected flat skill file")
    for path in paths:
        data = _frontmatter(path, findings)
        if data is not None:
            if data.get("name") != path.parent.name:
                findings.append(
                    f"{path}: name must match directory '{path.parent.name}'"
                )
            _check_description(path, data, findings)
    return findings


def check_compliance_coverage(root: Path) -> list[str]:
    """Compare actual IDs, registry keys and the agreed 17-skill collection.

    Read the literal registry with AST so this gate neither needs an installed
    OmniCursor nor accidentally imports a different checkout for --root fixtures.
    """
    findings: list[str] = []
    discovered = {p.parent.name for p in (root / "skills").glob("*/SKILL.md")}
    if discovered != EXPECTED_SKILL_IDS:
        findings.append(
            "skills: expected exactly 17 IDs; "
            f"missing={sorted(EXPECTED_SKILL_IDS - discovered)}, "
            f"unexpected={sorted(discovered - EXPECTED_SKILL_IDS)}"
        )
    path = root / "src/omnicursor/compliance.py"
    try:
        tree = ast.parse(path.read_text())
        registry = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "COMPLIANCE_REGISTRY"
        )
        if not isinstance(registry, dict):
            raise ValueError("registry must be a literal dict")
        if set(registry) != discovered:
            findings.append("compliance registry IDs differ from discovered skills")
        if set(registry) != EXPECTED_SKILL_IDS:
            findings.append("compliance registry must contain the expected 17 IDs")
    except (OSError, SyntaxError, ValueError, StopIteration) as exc:
        findings.append(f"{path}: cannot read compliance registry ({exc})")
    return findings


def check_agents(root: Path) -> list[str]:
    findings: list[str] = []
    categories: dict[str, str] = {}
    directory = root / "agents"
    if not directory.is_dir():
        return ["agents: missing directory"]
    paths = sorted(directory.glob("*.json"))
    if not paths:
        return ["agents: empty collection (no JSON profiles)"]
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(f"{path}: invalid JSON ({exc})")
            continue
        if not isinstance(data, dict):
            findings.append(f"{path}: profile must be a JSON object")
            continue
        for field in AGENT_REQUIRED_FIELDS:
            if not data.get(field):
                findings.append(f"{path}: missing required field '{field}'")
        _check_description(path, data, findings)
        patterns = data.get("activation_patterns")
        if isinstance(patterns, dict):
            for key in ACTIVATION_REQUIRED_KEYS:
                if key not in patterns:
                    findings.append(f"{path}: activation_patterns missing '{key}'")
        else:
            findings.append(f"{path}: activation_patterns must be an object")
        category = data.get("category")
        if isinstance(category, str) and category:
            if category in categories:
                findings.append(
                    f"{path}: duplicate category '{category}' (also {categories[category]})"
                )
            else:
                categories[category] = path.name
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repo root (default: two levels above this script)",
    )
    parser.add_argument("--compliance-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    findings = check_compliance_coverage(root)
    if not args.compliance_only:
        findings += check_skills(root) + check_agents(root)
    for finding in findings:
        print(f"FRONTMATTER GATE: {finding}")
    if findings:
        return 1
    print("frontmatter gate: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

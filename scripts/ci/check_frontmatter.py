#!/usr/bin/env python3
"""CI gate (A10.7): skill frontmatter + agent config validation.

Catches the exact defect classes Phase-1 A9 fixed so they cannot regress:
  - broken/degenerate skill descriptions (hostile-reviewer's folded value was
    literally ``---``; execute-plan's was truncated mid-sentence),
  - dual-location drift between skills/<slug>.md and
    .cursor/skills/onex-<slug>/SKILL.md (both directions + byte parity),
  - agent configs missing required fields,
  - duplicate agent categories (the pr-review/address-pr-comments collision;
    hard uniqueness encodes the A9 `review-response` disambiguation — drop to
    an allowlist if the team later rules categories may repeat).

Exit 0 = clean; exit 1 = findings printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

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
    canonical = {
        f.stem: f
        for f in sorted((root / "skills").glob("*.md"))
        if f.name != "README.md"
    }
    # A gate reports findings; it never dies with a traceback on a missing dir.
    mirrors_dir = root / ".cursor" / "skills"
    mirrors = (
        {
            d.name.removeprefix("onex-"): d / "SKILL.md"
            for d in sorted(mirrors_dir.iterdir())
            if d.is_dir() and (d / "SKILL.md").exists()
        }
        if mirrors_dir.is_dir()
        else {}
    )

    for slug, path in canonical.items():
        data = _frontmatter(path, findings)
        if data is not None:
            if not data.get("name"):
                findings.append(f"{path}: missing 'name'")
            _check_description(path, data, findings)
        mirror = mirrors.get(slug)
        if mirror is None:
            findings.append(f"{path}: no mirror at .cursor/skills/onex-{slug}/SKILL.md")
        elif path.read_bytes() != mirror.read_bytes():
            findings.append(f"{path}: differs from {mirror} (dual-location parity)")
    for slug, mirror in mirrors.items():
        if slug not in canonical:
            findings.append(f"{mirror}: no canonical skills/{slug}.md")
    return findings


def check_agents(root: Path) -> list[str]:
    findings: list[str] = []
    categories: dict[str, str] = {}
    for path in sorted((root / ".cursor" / "agents").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(f"{path}: invalid JSON ({exc})")
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
    args = parser.parse_args()
    root = args.root.resolve()

    findings = check_skills(root) + check_agents(root)
    for finding in findings:
        print(f"FRONTMATTER GATE: {finding}")
    if findings:
        return 1
    print("frontmatter gate: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

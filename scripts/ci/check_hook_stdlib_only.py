#!/usr/bin/env python3
"""CI gate (A10.7): hooks must import Python stdlib + first-party code only.

The hook scripts run under whatever ``python3`` Cursor resolves — no venv, no
pip dependencies. Importing ``omnimarket``/``omnibase_core``/``pydantic``/
``yaml`` from a hook would break every install (and would violate the
"shared daemon, not shared import" transport ruling). First-party imports are
allowed: the modules in ``.cursor/hooks/lib/`` and the ``omnicursor`` package
(hooks put ``src/`` on sys.path; the 3.9-smoke tests keep those code paths
stdlib-clean transitively).

The one known near-miss stays legal by construction: ``daemon_ensure.py``
carries ``import omnimarket...`` **inside a string** (the detached wrapper's
import-check) — strings are not imports and don't reach the AST import nodes.

Exit 0 = clean; exit 1 = findings printed to stdout.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def _allowed_modules(root: Path) -> set[str]:
    allowed = set(sys.stdlib_module_names)
    allowed.add("omnicursor")  # first-party, via the hooks' src/ sys.path insert
    for lib_file in (root / ".cursor" / "hooks" / "lib").glob("*.py"):
        allowed.add(lib_file.stem)  # first-party hook lib, via the lib/ insert
    return allowed


def check_file(path: Path, allowed: set[str]) -> list[str]:
    findings: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import — first-party by definition
                continue
            names = [node.module] if node.module else []
        else:
            continue
        for name in names:
            top = name.split(".")[0]
            if top not in allowed:
                findings.append(
                    f"{path}:{node.lineno}: non-stdlib import '{name}' — hooks "
                    "must be stdlib + first-party only (delegate via the shared "
                    "emit daemon, never import platform packages)"
                )
    return findings


def check(root: Path) -> list[str]:
    allowed = _allowed_modules(root)
    findings: list[str] = []
    for path in sorted((root / ".cursor" / "hooks").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        findings.extend(check_file(path, allowed))
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
        print(f"STDLIB GATE: {finding}")
    if findings:
        return 1
    print("hook stdlib-only gate: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

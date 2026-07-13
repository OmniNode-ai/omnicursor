#!/usr/bin/env python3
"""CI gate (A10.7): no hardcoded ``onex.*`` topic literals under .cursor/hooks/.

Jonah's OMN-13944 analog for this fork (PR #4 review follow-up): hooks emit
**registry semantic keys** (``cursor.hook.prompt``, ``tool.executed``, ...) —
the topic strings live only in ``config/event_registry/omnicursor.yaml``. A
full ``onex.*`` literal in hook code is a bug even when it names the right
topic: it bypasses the registry as the single source of truth.

Mechanics: AST scan of every string constant (f-string parts included) in
``.cursor/hooks/**/*.py``. Docstrings are exempt (prose may *reference* a
topic); comments never reach the AST. Test files asserting the *absence* of
literals live under tests/, outside this gate's scope by construction.

Exit 0 = clean; exit 1 = findings printed to stdout.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

PATTERN = "onex."


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """ids() of string constants that are docstrings."""
    doc_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                doc_ids.add(id(body[0].value))
    return doc_ids


def check_file(path: Path) -> list[str]:
    findings: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and PATTERN in node.value
            and id(node) not in docstrings
        ):
            findings.append(
                f"{path}:{node.lineno}: hardcoded topic literal {node.value!r} — "
                "emit a registry semantic key instead (see config/event_registry/)"
            )
    return findings


def check(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted((root / ".cursor" / "hooks").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        findings.extend(check_file(path))
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
        print(f"TOPIC-LITERAL GATE: {finding}")
    if findings:
        return 1
    print("topic-literal gate: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

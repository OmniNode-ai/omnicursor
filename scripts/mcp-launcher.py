#!/usr/bin/env python3
"""Load MCP from the plugin copy; optional dependencies belong to its interpreter."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> plugin root
_SRC = _ROOT / "src"

if not (_SRC / "omnicursor").is_dir():
    sys.stderr.write(
        f"omnicursor MCP launcher: no src/omnicursor under plugin root {_ROOT}\n"
    )
    sys.exit(1)

sys.path.insert(0, str(_SRC))

try:
    from omnicursor.mcp.omnimarket_bridge_server import main
except ModuleNotFoundError as exc:
    if exc.name != "mcp":
        raise
    sys.stderr.write(
        f"omnicursor MCP launcher: {sys.executable} is missing mcp; "
        "configure Cursor's python3 with Python >=3.10 and omnicursor[mcp] "
        "installed externally. The plugin installer does not install packages.\n"
    )
    sys.exit(1)

main()

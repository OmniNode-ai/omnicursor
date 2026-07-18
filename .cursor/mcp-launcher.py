#!/usr/bin/env python3
"""Plugin-root-resolving MCP launcher (PR #10 review, point 4).

`.cursor/mcp.json` previously launched ``python3 -m omnicursor.mcp`` with
``PYTHONPATH=${workspaceFolder}/src`` — correct only when the workspace *is*
this checkout. In an arbitrary host workspace the staged plugin's ``src`` is
elsewhere, so the import silently depended on a separate install into the
exact interpreter Cursor spawns.

This launcher resolves the plugin root from its own real location — the same
``Path(__file__).resolve()`` idiom the hooks use — so the server imports from
the checkout the plugin was staged from, regardless of workspace or symlink
chain (install-plugin.sh stages per-entry symlinks back into the repo).
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent  # .cursor/ -> plugin root
_SRC = _ROOT / "src"

if not (_SRC / "omnicursor").is_dir():
    sys.stderr.write(
        f"omnicursor MCP launcher: no src/omnicursor under plugin root {_ROOT}\n"
    )
    sys.exit(1)

sys.path.insert(0, str(_SRC))

from omnicursor.mcp.omnimarket_bridge_server import main  # noqa: E402

main()

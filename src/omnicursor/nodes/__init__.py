"""OmniCursor node contracts (YAML), mirroring OmniClaude's per-node ``contract.yaml`` layout.

**Execution** is Cursor-native: each contract's ``cursor_native`` block must match an
entry in ``hooks/hooks.json``. Hook scripts stay under ``hooks/`` and
remain stdlib-only — they cannot import this package.

See ``docs/dev/OMNICURSOR_NODE_CONTRACTS.md``.
"""

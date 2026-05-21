# Cursor configuration

This directory holds OmniCursor plugin assets: rules, hooks, agents, and skills. End users install via **`./scripts/install-plugin.sh`** (symlink to `~/.cursor/plugins/local/omnicursor`); see [QUICKSTART](../docs/QUICKSTART.md).

| Subfolder | Purpose |
|-----------|---------|
| [`rules/`](./rules/) | `.mdc` rules — always-on guardrails + activatable methodology (buckets 1–3). |
| [`hooks/`](./hooks/) | Python **stdlib-only** scripts wired by [`hooks.json`](./hooks.json). |
| [`agents/`](./agents/) | JSON agent definitions merged with base categories in `src/omnicursor/agents.py`. |

**Also here:** [`hooks.json`](./hooks.json) — maps Cursor lifecycle events (`beforeSubmitPrompt`, `beforeShellExecution`, etc.) to hook scripts.

**Docs:** [Root README](../README.md), [Quickstart](../docs/QUICKSTART.md), [CLAUDE.md](../CLAUDE.md) (commands and constraints).

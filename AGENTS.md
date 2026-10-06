# AGENTS.md

Entry-point guidance is in [`CLAUDE.md`](./CLAUDE.md) (commands, architecture,
source-of-truth hierarchy). Read it first. This file adds only cloud-agent-specific notes.

## Cursor Cloud specific instructions

- **This is a Cursor plugin, not a server app.** The real product surfaces
  (rules/skills/agents/hooks) only execute inside the Cursor IDE. Cloud/background
  agents cannot load the plugin, so "running the app" here means exercising the same
  logic directly: the deterministic hook scripts, the agent-routing engine, the pytest
  suite, and the MCP bridge server. There is nothing to `curl` and no long-running
  service to start.
- **Use the venv.** The startup/update script creates `.venv` (gitignored) and installs
  `.[dev,mcp,ci]`. Activate it (`source .venv/bin/activate`) or call tools via
  `.venv/bin/<tool>`. The base image's `python3` has no project deps.
- **Standard commands live in `CLAUDE.md`** (setup, `pytest`, `ruff`, mypy) and
  `.githooks/pre-commit` (the full local gate). Lint/format scope is exactly
  `src/ tests/ hooks/ scripts/ci/`. Node-contract tests are a separate path:
  `pytest src/omnicursor/nodes`.
- **Ruff is intentionally unpinned** but `pyproject.toml` pins the lint rule set
  (`select = ["E4","E7","E9","F"]`), so a newer ruff (e.g. 0.16.x) stays green. Do not
  "fix" a flood of new lint findings by widening the tree — that's a deliberate
  follow-up, not a tooling regression.
- **Exercise the hooks the way Cursor does:** pipe a JSON object on stdin, read JSON on
  stdout — e.g. `echo '{"command":"rm -rf /"}' | python3 hooks/scripts/shell-guard.py`
  (denies), or feed `{"conversation_id":...,"prompt":...}` to
  `hooks/scripts/user-prompt-submit.py` (routing decisions are appended to
  `~/.omnicursor/events.jsonl`, not stdout).
- **Hook side-effect paths are fixed to `~/.omnicursor/`** (`events.jsonl`, `sessions/`,
  `learned_patterns.json`, `outbox.jsonl`). `OMNICURSOR_DATA_DIR` does **not** relocate
  the event log. To isolate a test run, use a temporary HOME, temporary socket and explicit
  `OMNICURSOR_DAEMON_PYTHON`; preserve existing user logs.
- **Use one hook source at a time.** Disable the installed plugin while developing
  through `.cursor/hooks.json`. Test the plugin in a foreign workspace without the
  shim; its copy must be reinstalled after changes.
- **MCP bridge server** (`omnicursor-omnimarket`) needs the optional `[mcp]` extra and,
  to actually invoke nodes, `OMNIMARKET_ROOT` pointing at a local omnimarket checkout
  (absent here). It still loads and lists its 3 tools without that checkout — good enough
  for a smoke test; real tool calls require the checkout.
- **Docker `compose.yaml` is optional and network-gated** (intelligence images build from
  a remote GitHub ref). It is not needed for the core dev/test loop; skip it unless a task
  explicitly targets the event-emission / Option-B tiers.

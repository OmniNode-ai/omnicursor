# OmniCursor node contracts (OmniClaude-shaped, Cursor-native)

OmniClaude expresses deployable units as **`src/omniclaude/nodes/*/contract.yaml`**: orchestrators, effects, and adapters, discovered via **Kafka-backed** contract registration in the ONEX runtime.

OmniCursor keeps the **same artifact shape** (per-node directory + `contract.yaml`) under **`src/omnicursor/nodes/`**, but **replaces the event bus with Cursor**:

| OmniClaude | OmniCursor |
|------------|------------|
| `event_bus.subscribe` / Kafka topics | **`cursor_native.hook_event`** + **`.cursor/hooks.json`** |
| Handler modules in `src/omniclaude/...` | **`.cursor/hooks/*.py`** (stdlib only — cannot import `omnicursor`) |
| `ModelContractRegisteredEvent` / runtime discovery | **Install-time / CI**: `omnicursor.node_contracts` + tests |
| Optional `~/.claude` / emit socket | **`~/.omnicursor/events.jsonl`** (append-only log; optional) |

## Source of truth

1. **`contract.yaml`** — documents the node (name, type, description, capabilities, **Cursor binding**).
2. **`.cursor/hooks.json`** — the executable registry Cursor loads. Every contract’s `cursor_native.hooks_json_command` must appear under the matching `hook_event` key.
3. **Hook script** — `cursor_native.implementation`; must stay stdlib-only per `CLAUDE.md`.
4. **`handler.py`** (next to `contract.yaml`) — thin **library** surface: documents the same binding (`hook_binding()`) for tests and tooling. May import `omnicursor` (e.g. `prompt_pattern_read`, which loads stdlib helpers from `.cursor/hooks/lib/`). **Hook scripts must not `import omnicursor`**; they use `lib/*.py` only.

When adding a new lifecycle integration, add or extend a contract **and** register the command in `hooks.json` in the same change.

## Python API

- `omnicursor.node_contracts.iter_contract_paths()` — discover YAML files.
- `omnicursor.node_contracts.load_all_contracts()` — parse and validate (Pydantic).
- `omnicursor.node_contracts.hooks_registration_ok()` — dev check that `hooks.json` matches loaded contracts (expects an OmniCursor repo layout).

## Tests

`tests/test_node_contracts.py` asserts all contracts parse and that `hooks.json` matches when tests run from the repository. `tests/test_node_handlers.py` asserts each `handler.py` matches its contract. Pattern read logic is covered by `tests/test_prompt_pattern_read.py` and `omnicursor.prompt_pattern_read`.

## Related

- [`OMNICLAUDE_TO_CURSOR_PORT.md`](./OMNICLAUDE_TO_CURSOR_PORT.md) — how OmniClaude-style behavior maps to Cursor hooks + library (shared pattern code, duplicated routing).
- [`ADR-hook-first-architecture.md`](./ADR-hook-first-architecture.md) — hooks vs rules vs library.
- [`CURSOR_VS_CLAUDE_HOOKS.md`](./CURSOR_VS_CLAUDE_HOOKS.md) — lifecycle parity matrix.

# Changelog

All notable changes to OmniCursor are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MIT `LICENSE` at repo root (OmniNode org standard). (#1)
- Real Cursor hook contract coverage: `sessionStart`, `postToolUse`, and
  `sessionEnd` hooks join the original four — 7 lifecycle hooks total — plus
  pattern-based context injection via `sessionStart`/`postToolUse`
  `additional_context`. (#4)
- Shared emit-daemon provisioning (A2): `lib/daemon_ensure.py` pings the
  platform `node_emit_daemon` on the pinned socket and spawns it detached when
  absent (mandatory Kafka `localhost:19092`, spawn-stamp dedupe), triggered
  from `sessionStart` with a first-prompt fallback; launchd/systemd user
  templates under `provisioning/`. (#5)
- Canonical hook events (A3/A4): every hook emits registry **semantic keys**
  (never topic literals); the prompt path builds the canonical
  `ModelCursorHookEvent` shape (`agent_source="cursor"`, native→canonical
  event-type normalization, full-UUID `correlation_id`) fanned out by
  `config/event_registry/omnicursor.yaml` (8 keys, `tier` on every rule) to
  the merged backend consumer topic. (#5)
- Secret redaction (A5): `lib/redaction.py` (pattern table byte-identical to
  the omniclaude donor) applied to every emitted or locally persisted prompt
  fragment, command preview, and injected pattern text. (#5)
- Kill-switch + per-hook mask (A6): `OMNICURSOR_HOOKS_DISABLE=1` or the
  `~/.omnicursor/hooks-disabled` marker short-circuits all 7 hooks before any
  side effect; `OMNICURSOR_HOOKS_MASK` allowlists individual hooks. (#6)
- `sessionStart` injection evidence (Cursor 3.10.11, local IDE), scoped to
  "local `sessionStart` injection confirmed". (#4, #7)
- `CHANGELOG.md` (this file) (A10.1).
- `.cursor/mcp.json` shipped and tracked (previously gitignored), registering
  the `omnicursor-omnimarket` FastMCP bridge; referenced from the plugin
  manifest (A10.3).
- `--purge` flag for `install-plugin.sh --uninstall`: opt-in removal of
  `~/.omnicursor/` local data (A10.5).
- Hardened CI: manifest schema validation, skill/agent frontmatter gate,
  hook topic-literal gate, stdlib-only hook import guard, dual-location skill
  parity, agent-category uniqueness, shellcheck, secret scan, README link
  check, ruff format check (A10.7).

### Changed
- Documentation sanitized for OSS (local-env examples, `OMN-XXXX`
  placeholders). (#2)
- Emit transport routed through the shared platform `node_emit_daemon` over
  the Unix socket instead of the bespoke sidecar/drainer pair. (#3)
- `pattern_sync.py` adopts `INTELLIGENCE_SERVICE_URL` (deprecated fallback:
  `OMNIINTELLIGENCE_URL` for one release). (#6)
- Single canonical manifest: `.cursor-plugin/plugin.json`; the homegrown root
  `cursor-plugin.json` is removed, its `requires`/`install` facts preserved in
  README and `pyproject.toml` (A10.2).
- `install-plugin.sh` installs a curated runtime payload instead of
  symlinking the whole repository (no `tests/`, `.git`, `docker/`, `eval/`,
  `compose.yaml` in the installed plugin) (A10.4).
- README rewritten for installers: Requirements, Privacy, Uninstall, and MCP
  setup sections (A10.6).

### Fixed
- `shell-guard.py` fail-open: a telemetry-emit failure could downgrade a
  computed `deny`/`ask` to `allow`; the decision is now written to stdout
  before the emit, which is isolated in its own `try/except`. (#5)
- Audit log privacy: `shell-guard.py` redacts secrets from the raw command
  before persisting to `~/.omnicursor/events.jsonl`; `session-end.py` redacts
  `error_message`. (#5, #6)
- Broken/truncated skill frontmatter (`hostile-reviewer`, `execute-plan` —
  both copies of each) and the `review` agent-category collision
  (`address-pr-comments` → `review-response`). (#6)

### Removed
- Bespoke `sidecar/` + `drainer/` transport (replaced by the shared platform
  daemon). (#3)
- Dead legacy hook set (`.cursor/hooks/on_*.py`) and root `_common.py` /
  `pattern_loader.py` duplicates. (#4)
- Root `cursor-plugin.json` manifest (A10.2).

## [0.1.0] - 2026-05-21

### Added
- Initial Cursor-native plugin: rules, 4 lifecycle hooks (`beforeSubmitPrompt`,
  `beforeShellExecution`, `afterFileEdit`, `stop`), 17 skills, 17 agents,
  official manifest `.cursor-plugin/plugin.json`, and
  `scripts/install-plugin.sh`.

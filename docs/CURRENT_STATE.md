# Current State

> **Snapshot date:** July 2026 · **Package version:** `0.1.0`
> This document describes *what actually works today*. For *how it is designed*,
> read [`ARCHITECTURE.md`](./ARCHITECTURE.md). When this doc and the code
> disagree, the code wins.

## At a glance

| Metric | Value | Verified by |
|--------|-------|-------------|
| Cursor rules (`.mdc`) | **14** | `.cursor/rules/*.mdc` |
| File-backed skills | **17** (× 2 locations) | `skills/*.md` (excl. `README.md`), `.cursor/skills/onex-*/SKILL.md` |
| Agent configs | **17** | `.cursor/agents/*.json` |
| Active hooks | **7** | `.cursor/hooks.json` |
| Node contracts | **7** (one per hook event) | `src/omnicursor/nodes/*/contract.yaml` |
| Test functions | **759** across **36** test files | `tests/` (704/31) + `src/omnicursor/nodes/*/tests/` (55/5) |
| Compliance smoke-checks | **17** keys | `src/omnicursor/compliance.py` |

---

## Works fully offline (core plugin)

These need only the plugin symlink — no network, no Docker, no extra deps:

- ✅ **Rules** load and apply (`00`–`03` always-on; `10`–`19` on keyword/`@mention`).
- ✅ **Skills** are discoverable via the Cursor `/` picker and readable by the model.
- ✅ **Context injection** — `sessionStart` injects session-level context
  (baseline patterns + delegation rule + prior session) via `additional_context`;
  `postToolUse` refreshes it. This is Cursor's real injection channel.
- ✅ **Agent routing** — the `beforeSubmitPrompt` hook scores prompts and emits the
  classification + relevant patterns for backend learning (block-only; no injection).
- ✅ **Shell guard** — the one hook that can deny: 9 HARD_BLOCK (deny) + 12
  SOFT_WARN (allow + warning). Output `{permission, user_message, agent_message}`.
- ✅ **Post-edit diagnostics** — `ruff` / `tsc --noEmit` on edited files (read-only).
- ✅ **Session lifecycle** — `stop` classifies outcome (loop-end); `sessionEnd`
  emits the true conversation-close event.
- ✅ **Option A pattern learning** — local read/inject/reinforce at
  `~/.omnicursor/learned_patterns.json`.
- ✅ **Python library + test suite** — `pip install -e ".[dev]" && pytest tests/`.

> **Injection channel (resolved in W4):** Cursor's `beforeSubmitPrompt` output is
> block-only (`{continue, user_message}`) and does **not** consume `systemMessage` —
> the earlier per-prompt injection was a structural no-op. Injection now flows through
> `sessionStart.additional_context` (initial) and `postToolUse.additional_context`
> (refresh), per the live Cursor hooks docs. `sessionStart` injection is **proven**
> on Cursor 3.10.11 (local IDE) — see [`W4_INJECTION_EVIDENCE.md`](./W4_INJECTION_EVIDENCE.md)
> for the scoped verdict, the `OMNICURSOR_INJECTION_SENTINEL=1` receipt protocol,
> and the open residuals (R1: `postToolUse` unproven; R2: N=1; R3: cloud; R4: other builds).

---

## Opt-in tiers (require setup)

| Capability | What you need | Default |
|------------|---------------|---------|
| **Linear ticketing** (Bucket 3 skills) | Linear MCP configured in `~/.cursor/mcp.json` | off |
| **OmniMarket bridge / MCP tools** | `OMNIMARKET_ROOT` → local checkout; `pip install -e ".[mcp]"`; `gh` CLI for `run_ci_watch` | off |
| **Option B** — HTTP pattern pull | `OMNICURSOR_PATTERN_SYNC_HTTP=1`, `INTELLIGENCE_SERVICE_URL` (`OMNIINTELLIGENCE_URL` = deprecated fallback); running omniintelligence | **off** |
| **Event emission** — bus events via the shared platform emit daemon | omnimarket `node_emit_daemon` owning `~/.omnicursor/emit.sock` (see ARCHITECTURE §8) | off |
| **Local OmniNode stack** | `docker compose up -d` (Postgres, Redpanda, Valkey, intelligence; `--profile memory` adds Qdrant/Memgraph/Kreuzberg) | off |

> The intelligence services in `compose.yaml` build from a **remote GitHub ref**
> (`OmniNode-ai/omniintelligence#${OMNIINTELLIGENCE_REF}`) at build time — network
> + repo access required.

---

## Component status

| Component | Status | Notes |
|-----------|--------|-------|
| Rules / skills / agents | ✅ Working | Counts above |
| Prompt routing (`scoring.py`) | ✅ Working | CI-gated: macro precision ≥ 0.80, recall ≥ 0.60 over ≥100 labeled prompts |
| Shell guard | ✅ Working | DoD/dispatch gates present but **default-off** |
| Post-edit, stop hooks | ✅ Working | Informational only (Cursor ignores stdout) |
| Pattern learning (Option A) | ✅ Working | Constants marked *v0, unevaluated* |
| Node contracts | ✅ Loading/validating | In-process node surface drops some fields (see drift) |
| OmniMarket bridge | ⚠️ Needs a checkout | Subprocess-only; errors unless `OMNIMARKET_ROOT` is set or an `omnimarket-main/` dir exists |
| MCP server | ⚠️ Needs `[mcp]` extra | 3 tools |
| Event emission (shared emit daemon) | ⚠️ Opt-in | Hooks emit best-effort to `emit.sock`; the shared platform `node_emit_daemon` owns it (ARCHITECTURE §8) |
| Option B HTTP sync | ⚠️ Opt-in / dev only | Default off |

---

## Known drift & gotchas

Honest list of things that surprise readers. None are blockers for the core
plugin, but they shape any work in these areas.

1. **Single hook implementation.** `.cursor/hooks/scripts/*.py` (delegating to
   `.cursor/hooks/lib/*.py`) are the only entrypoints; the legacy top-level
   `on_*.py` set was deleted in W4. See ARCHITECTURE §4.
2. **Skill dual-path asymmetry.** Runtime loads from `.cursor/skills/` only; CI
   scans `skills/`. They must be content-identical (UTF-8 text; enforced by a parity test).
3. **7 contracts / 7 hooks.** One contract per hook event (sessionStart,
   beforeSubmitPrompt, beforeShellExecution, afterFileEdit, postToolUse, stop, sessionEnd).
4. **In-process node fields dropped.** Shell-guard soft-warn message and file-edit
   `tsc` findings are computed but not surfaced by the node output models.
5. **Env var split — resolved.** Both the per-prompt fetch and the session-end
   sync now read `INTELLIGENCE_SERVICE_URL`; `OMNIINTELLIGENCE_URL` survives
   only as a deprecated fallback in the sync path (one release).
6. **`.env.omninode.example` ships `OMNICURSOR_PATTERN_SYNC_HTTP=1`** even though
   the documented default is off — copying it verbatim silently enables Option B.
7. **Fallback name split.** `omnicursor-generalist` (library) vs
   `polymorphic-agent` (eval/CI).
8. **No `[tool.ruff]` config and unpinned ruff** — a ruff release can change lint
   results with no repo change.

---

## Tests & CI

- **Suite shape (3 tiers):** (a) library/unit tests; (b) four
  `test_suite_eventN_*.py` that `importlib`-load the real `.cursor/hooks/scripts/*.py`
  and exercise each lifecycle event; (c) the routing eval gate
  (`test_routing_eval.py`) + manual human-graded prompts/rubrics under
  `tests/prompts/` and `tests/rubrics/`.
- **CI** (`.github/workflows/ci.yml`): runs on **pull requests to `main`,
  pushes to `main`, `workflow_dispatch`, and a weekly schedule** (A10.7 +
  the #12 hardening pass). Jobs — all secret-free/fork-safe: `lint-and-test`
  (ruff check + `ruff format --check` + pytest with the `.[dev,mcp]` extras
  so the MCP-launcher sandbox smoke runs hosted + skill-coverage substring
  check), `typecheck` (mypy over `src/`), `plugin-gates` (`scripts/ci/`:
  manifest validated against the **pinned official cursor/plugins schema**
  (`schemas/cursor-plugin.schema.json`, provenance in `schemas/README.md`)
  plus MCP wiring, skill/agent frontmatter + dual-location parity +
  category uniqueness, hardcoded-topic-literal guard over `.cursor/hooks/`,
  hook stdlib-only imports, shellcheck), `security` (bandit; detect-secrets
  vs the audited `.secrets.baseline`), `links` (offline lychee over
  README/CHANGELOG/docs), `sibling-drift` (checks out
  `omnimarket`/`omnibase_core` at **governed pin SHAs** on PR/push runs —
  deterministic for a given PR SHA — while the weekly scheduled run probes
  the moving `dev` heads non-blockingly), and the `ci-summary` aggregate for
  branch protection.
- **Pre-commit** (`.githooks/pre-commit`, enable with
  `git config core.hooksPath .githooks`): mirrors the fast local subset —
  ruff check + format, pytest, skill coverage, and the four `scripts/ci/`
  plugin gates. Bypass only with `git commit --no-verify`.
- The **strict** skill-coverage gate is `tests/test_compliance.py` /
  `tests/test_skills.py` (exact 17-key sets), not the looser CI substring snippet.

---

## Branches

| Branch | Notes |
|--------|-------|
| `main` | Default — full plugin, routing, hooks, Options A/B sources, tests |
| Feature branches (`awu42/*`, `julian/*`, …) | In-flight work — check `git branch -a`. Historical topic branches (e.g. `intelligence/option-b`) live on contributors' forks, not this repo |

---

## Not implemented / out of scope

- In-process omnimarket handler fallback (docs mention it; code is subprocess-only).
- Bridging pattern **writes** to upstream intelligence (year-2 / out of capstone scope).
- Real *behavioral* compliance — current `check_compliance` is a **vocabulary
  smoke-check** only (a well-worded response can pass without doing real work).
- `onex run <contract.yaml>` as a bridge path (broken upstream).

---

**See also:** [`ARCHITECTURE.md`](./ARCHITECTURE.md) ·
[`QUICKSTART.md`](./QUICKSTART.md) · [`INDEX.md`](./INDEX.md)

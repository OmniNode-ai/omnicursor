# Current State

> **Snapshot date:** June 2026 · **Package version:** `0.1.0`
> This document describes *what actually works today*. For *how it is designed*,
> read [`ARCHITECTURE.md`](./ARCHITECTURE.md). When this doc and the code
> disagree, the code wins.

## At a glance

| Metric | Value | Verified by |
|--------|-------|-------------|
| Cursor rules (`.mdc`) | **14** | `.cursor/rules/*.mdc` |
| File-backed skills | **17** (× 2 locations) | `skills/*.md` (excl. `README.md`), `.cursor/skills/onex-*/SKILL.md` |
| Agent configs | **17** | `.cursor/agents/*.json` |
| Active hooks | **4** | `.cursor/hooks.json` |
| Node contracts | **5** (for 4 hook events) | `src/omnicursor/nodes/*/contract.yaml` |
| Test functions | **671** across **28** test files | `tests/` |
| Compliance smoke-checks | **17** keys | `src/omnicursor/compliance.py` |

---

## Works fully offline (core plugin)

These need only the plugin symlink — no network, no Docker, no extra deps:

- ✅ **Rules** load and apply (`00`–`03` always-on; `10`–`19` on keyword/`@mention`).
- ✅ **Skills** are discoverable via the Cursor `/` picker and readable by the model.
- ✅ **Agent routing** — the prompt hook scores prompts and injects an agent
  persona + learned patterns (`beforeSubmitPrompt`).
- ✅ **Shell guard** — the one hook that can deny: 9 HARD_BLOCK (deny) + 12
  SOFT_WARN (allow + warning).
- ✅ **Post-edit diagnostics** — `ruff` / `tsc --noEmit` on edited files (read-only).
- ✅ **Session outcome** — the `stop` hook classifies failed/success/abandoned/unknown.
- ✅ **Option A pattern learning** — local read/inject/reinforce at
  `~/.omnicursor/learned_patterns.json`.
- ✅ **Python library + test suite** — `pip install -e ".[dev]" && pytest tests/`.

> **Platform uncertainty:** whether Cursor actually *renders/consumes* the
> `systemMessage` the prompt hook emits (agent persona, delegation nudge, recap)
> is **not confirmed**. The hook always emits it; the shell-guard `deny` is the
> only hook output Cursor is known to act on.

---

## Opt-in tiers (require setup)

| Capability | What you need | Default |
|------------|---------------|---------|
| **Linear ticketing** (Bucket 3 skills) | Linear MCP configured in `~/.cursor/mcp.json` | off |
| **OmniMarket bridge / MCP tools** | `OMNIMARKET_ROOT` → local checkout; `pip install -e ".[mcp]"`; `gh` CLI for `run_ci_watch` | off |
| **Option B** — HTTP pattern pull | `OMNICURSOR_PATTERN_SYNC_HTTP=1`, `OMNIINTELLIGENCE_URL`; running omniintelligence | **off** |
| **Option C** — event pipeline | `scripts/run_sidecar.sh`, Redpanda/Kafka, **manually-installed** `confluent-kafka` | off |
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
| Drainer / sidecar (Option C) | ⚠️ Partial | See "Known drift" — socket→outbox bridge does not publish |
| Option B HTTP sync | ⚠️ Opt-in / dev only | Default off |

---

## Known drift & gotchas

Honest list of things that surprise readers. None are blockers for the core
plugin, but they shape any work in these areas.

1. **Two hook implementations.** `.cursor/hooks/scripts/*.py` are the wired,
   authoritative entrypoints. The top-level `.cursor/hooks/on_*.py` are
   **legacy/test-only** (not in `hooks.json`) and have drifted. See ARCHITECTURE §4.
2. **Skill dual-path asymmetry.** Runtime loads from `.cursor/skills/` only; CI
   scans `skills/`. They must be content-identical (UTF-8 text; enforced by a parity test).
3. **5 contracts / 4 hooks.** `beforeSubmitPrompt` is described by two nodes.
4. **In-process node fields dropped.** Shell-guard soft-warn message and file-edit
   `tsc` findings are computed but not surfaced by the node output models.
5. **Socket→outbox bridge is dead for publishing.** Only
   `omnicursor.session_outcome.v1` rows ever publish; `{event_type,payload}` rows
   appended via `emit.sock` are skipped by `transform`.
6. **Env var split.** `INTELLIGENCE_SERVICE_URL` (per-prompt fetch) vs
   `OMNIINTELLIGENCE_URL` (session-end sync) — different consumers.
7. **`.env.omninode.example` ships `OMNICURSOR_PATTERN_SYNC_HTTP=1`** even though
   the documented default is off — copying it verbatim silently enables Option B.
8. **Kafka bootstrap mismatch.** Sidecar default `localhost:29092` vs
   `run_bc_stack.sh` export `localhost:19092`.
9. **Fallback name split.** `omnicursor-generalist` (library) vs
   `polymorphic-agent` (eval/CI).
10. **No `[tool.ruff]` config and unpinned ruff** — a ruff release can change lint
    results with no repo change.
11. **`hostile-reviewer.md` has malformed/nested frontmatter** (a second
    OmniClaude YAML block embedded in the body).

---

## Tests & CI

- **Suite shape (3 tiers):** (a) library/unit tests; (b) four
  `test_suite_eventN_*.py` that `importlib`-load the real `.cursor/hooks/scripts/*.py`
  and exercise each lifecycle event; (c) the routing eval gate
  (`test_routing_eval.py`) + manual human-graded prompts/rubrics under
  `tests/prompts/` and `tests/rubrics/`.
- **CI** (`.github/workflows/ci.yml`): runs **only on pull requests to `main`**
  (no push trigger). Steps: `ruff check src/ tests/ .cursor/hooks/`,
  `pytest tests/ -v`, and an inline skill-coverage **substring** check.
- **Pre-commit** (`.githooks/pre-commit`, enable with
  `git config core.hooksPath .githooks`): mirrors the same three checks locally.
  Bypass only with `git commit --no-verify`.
- The **strict** skill-coverage gate is `tests/test_compliance.py` /
  `tests/test_skills.py` (exact 17-key sets), not the looser CI substring snippet.

---

## Branches

| Branch | Notes |
|--------|-------|
| `main` | Default — full plugin, routing, hooks, Options A/B/C sources, sidecar, tests |
| `intelligence/option-b`, `intelligence/option-c` | Topic/history branches — **diff against `main`** before assuming divergence |
| Feature branches (`awu42/omn-*`, `julian/*`, …) | In-flight work — check `git branch -a` |

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

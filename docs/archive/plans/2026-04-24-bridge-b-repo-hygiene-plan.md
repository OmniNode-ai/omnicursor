# BRIDGE-B: Repo Hygiene + Bridge Conventions

**Date:** 2026-04-24
**Source:** Sponsor alignment (2026-04-16) + context restore session
**Status:** Executed

---

## P0 — Gitignore `.env` and local artifacts

- **What:** Added `.env`, `.env.local`, `.env.*.local`, `omnimarket-main/`, `omnimarket-main.zip` to `.gitignore`.
- **Why:** `.env` contains credentials and was not ignored — any `git add .` would stage it. `omnimarket-main/` is a local checkout that must never be committed.
- **Acceptance criteria:** `git status` no longer shows `.env`, `omnimarket-main/`, or `omnimarket-main.zip` as untracked. `.env.omninode.example` remains trackable.
- **Files affected:** `.gitignore`

## P1 — Document `OMNIMARKET_ROOT` convention

- **What:** Added "## Omnimarket bridge" section to `CLAUDE.md` documenting:
  - `OMNIMARKET_ROOT` env var points to a local omnimarket checkout.
  - Fallback to `omnimarket-main/` in repo root (dev convenience only).
  - Omnimarket is never cloned at runtime.
  - Preferred invocation: `python -m omnimarket.nodes.<node>` via subprocess.
  - Out of scope: `onex run <contract.yaml>`, direct omniintelligence HTTP calls.
  - Docker Compose is approved but is not the primary bridge path.
- **Why:** The MCP bridge (next batch) needs this convention. Documenting constraints now prevents wrong-path implementation.
- **Acceptance criteria:** `grep -rn OMNIMARKET_ROOT CLAUDE.md` returns hits.
- **Files affected:** `CLAUDE.md`

## Verification

```bash
git status | grep -E '\.env$|omnimarket-main' && echo "FAIL" || echo "PASS"
grep -c 'OMNIMARKET_ROOT' CLAUDE.md
ruff check src/ tests/ .cursor/hooks/
pytest tests/ -v
```

## Out of scope

- Staging/committing Docker artifacts (`compose.yaml`, `docker/`, `docs/dev/OMNINODE_STACK.md`, `.env.omninode.example`) — follow-up batch
- MCP tool implementation (BRIDGE-C)
- Subprocess bridge code
- Docker Compose expansion
- `onex run` integration
- Direct omniintelligence HTTP calls
- Pattern writes to upstream

# Handoff — port track scope (2026-04-21)

## What changed

- **`docs/dev/MIGRATION_PHASES_HANDOFF.md`** is now **port-only**: agents (Phase A), skills (Phase B), ONEX nodes & contracts (Phase C), plus PR verification. Removed from that file: Phase 1 hook verification extras, Kafka (Phase 5), Linear-in-hooks (Phase 6), pattern HTTP/PG (Phase 7), and hook-integration cross-cutting items that are not part of the port role.
- **`docs/OMNICURSOR_MIGRATION_PLAN.md`** — added a **port track** pointer at the top; split **recommended start order** into *port track* vs *hooks / integration / bus*; simplified the execution diagram.
- **`docs/dev/SPONSOR_ALIGNMENT_2026-04-16.md`**, **`docs/dev/CURSOR_FEATURE_SURFACE_MAP.md`**, **`docs/dev/README.md`**, **`CLAUDE.md`**, **`docs/dev/HANDOFF.md`** — wording updated so the handoff doc describes the port checklist, not the hooks-only checklist.

## Next steps (port track)

1. Run Phase A / B / C checklists in `MIGRATION_PHASES_HANDOFF.md` in the order that unblocks your PRs (agents and skills often alternate in batches).
2. For full-repo hook, bus, Linear, MCP, and pattern-write work, use **`OMNICURSOR_MIGRATION_PLAN.md`** only — do not fold that into the port checklist unless scope changes.

## Verification

- `ruff check src/ tests/ .cursor/hooks/`
- `pytest tests/ -v`

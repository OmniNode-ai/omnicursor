# OmniCursor Session Handoff

**Date**: 2026-04-09
**Focus**: full codebase review, role alignment, architecture refresh, and updated capstone planning

## What Was Reviewed

- Core runtime:
  - `.cursor/hooks.json`
  - `.cursor/hooks/_common.py`
  - `.cursor/hooks/on_prompt.py`
  - `.cursor/hooks/on_shell.py`
  - `.cursor/hooks/on_stop.py`
  - `.cursor/hooks/pattern_loader.py`
  - `src/omnicursor/` (Python library)
  - `src/omnicursor/agents.py`
  - `src/omnicursor/compliance.py`
  - `src/omnicursor/skills.py`
  - `src/omnicursor/db.py`
  - `src/omnicursor/patterns.py`
- Planning / architecture inputs:
  - `OmniCursor_Architecture_FINALupdated33.docx`
  - `OmniCursor_DoD_Rubric.md`
  - `investigacion_omninode_ClaudeCode.md`
  - `docs/dev/HANDOFF.md`
  - `CLAUDE.md`
- Reference:
  - `omniclaude/`

## Key Findings

1. Phase 3A is genuinely complete at the architecture level.
2. The repo has a real three-layer system:
   - Rules
   - Hooks
   - Python library
3. The next bottlenecks are not "discovering the architecture" anymore. They are:
   - runtime proof in real Cursor
   - CI/CD automation
   - pattern write-path completion
   - clear OmniCursor -> OmniIntelligence integration planning
4. There is currently **no `.github/workflows/` directory** in the repo.
5. Local lint is clean, but local tests are not fully green:
   - `.venv/bin/ruff check src/ tests/ .cursor/hooks/` -> passes
   - `.venv/bin/pytest tests/ -q` -> `121 passed, 1 failed`
6. The current failing test is:
   - `tests/test_skills.py::test_available_skills_lists_all`
   - cause: `skills/README.md` is being included by `SkillRepository.available_skills()`
7. `docs/dev/handoffs/` did not exist before this session. It now exists through this handoff.

## Opinion / Direction

The team split is good, but only if the boundaries stay explicit:

- **CI / quality automation:** GitHub Actions, green baseline, test/lint/docs verification on push.
- **This repo (library + Cursor surface):** Python library (`src/omnicursor/`), hooks/rules integration, agent registry, routing, research on Cursor-side agents or plugin surfaces.
- **OmniClaude reuse inside OmniCursor:** Hooks integration, routing/runtime borrowing, pattern lifecycle path from OmniClaude concepts.
- **External ecosystem integration:** OmniIntelligence, OmniMemory, OmniDash, Dockerized local integration path.

This split reduces the biggest overlap risk: one lane owns what gets reused from OmniClaude inside this repo; another owns how OmniCursor connects outward to the rest of OmniNode.

## Files Created This Session

- `OmniCursor_Architecture_FINAL44.docx`
- `docs/dev/handoffs/2026-04-09-architecture-role-alignment.md`

## What Changed in the New Architecture Document

The new document keeps the existing structure/style but updates the content to reflect:

- current codebase reality
- completion of Phase 3A
- the new team role split
- role-specific next deliverables
- DoD-aligned completion criteria
- realistic risks and mitigations
- honest current verification status (`121 / 122` tests, lint clean)

## Recommended Next Actions

### CI / quality

- Create `.github/workflows/ci.yml`
- Make lint + tests run on push / PR
- Fix the `skills/README.md` regression in skill discovery
- Add docs validation if lightweight

### This repo (library + Cursor)

- Harden `src/omnicursor/agents.py` (and related library modules)
- Clarify whether "Cursor plugin" is a real near-term path or just a research track
- Document how OmniCursor should connect to Cursor agents/configs without assuming unsupported APIs

### OmniClaude reuse / patterns

- Continue extracting only the reusable hook/runtime patterns from `omniclaude/`
- Design or implement `store_pattern`
- Keep the JSON persistence path lightweight for MVP

### External integration

- Use `investigacion_omninode_ClaudeCode.md` to define the first realistic OmniCursor -> OmniIntelligence bridge
- Identify what should connect now vs later across OmniIntelligence, OmniMemory, OmniDash
- Build a minimal Dockerized local intelligence path for integration experiments

## Current Risk Register

- `beforeSubmitPrompt` may emit `systemMessage` without Cursor consuming it
- no CI pipeline yet
- one local regression already exists in test coverage
- plugin scope could create unnecessary scope creep
- OmniIntelligence integration could become too heavy if it is treated like full-platform parity

## Practical Summary

OmniCursor is no longer blocked on architectural confusion.

It is now in the execution phase where the team should:

1. restore a fully green automated baseline
2. complete the pattern write path
3. validate runtime behavior in real Cursor
4. define a believable integration runway into OmniIntelligence without turning the capstone into a full OmniNode rebuild

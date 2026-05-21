# Plan: OMN-46 — onex namespaced slash labels

**Linear:** [OMN-46](https://linear.app/omninode-capstone-winter2026/issue/OMN-46/expose-onex-namespaced-slash-labels-for-omnicursor-skills)

## Task 1: Expose onex namespaced slash labels for OmniCursor skills

### Description

Cursor `/` picker should surface canonical `onex-<slug>` (typically via subdirectory `.cursor/skills/onex-<slug>/`), consistent with README and compliance ids. Add YAML frontmatter to each `SKILL.md` per Cursor Agent Skills docs (`name`, `description`). If Cursor disallows `:` in `name`, use `onex-<slug>` in frontmatter and document the mapping to canonical `onex-<slug>` in README/QUICKSTART.

### Acceptance criteria

- Every `.cursor/skills/*/SKILL.md` includes YAML frontmatter with non-empty `name` and `description`.
- Automated check (pytest or small script exercised by pytest) asserts each skill’s frontmatter `name` starts with `onex` and uses allowed characters (colon or hyphen namespace), matching the mirrored set under `skills/`.
- README or `docs/QUICKSTART.md` updated: how canonical `onex-<slug>` relates to slash picker / frontmatter `name`.
- Manual: confirm in Cursor that `/` lists a skill with the intended namespaced label (note Cursor version in PR if relevant).

### Verification

- `ruff check src/ tests/ .cursor/hooks/`
- `pytest tests/ -v`

### blockedBy

_(none)_

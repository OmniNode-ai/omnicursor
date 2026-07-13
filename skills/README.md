# Skills (canonical source)

This directory holds the **canonical** skill Markdown — one `<slug>.md` per skill. CI's skill-compliance check scans `skills/*.md`, and each file must have a matching entry in `src/omnicursor/compliance.py`.

Cursor discovers skills from **mirrored** copies at `.cursor/skills/onex-<slug>/SKILL.md` (the `/` slash-picker uses each `onex-<slug>` directory name). Canonical skill ids are **`onex-<slug>`** — the same `<slug>` as the filename here.

Each skill has YAML frontmatter (`name:`, `description:`) followed by the skill instructions.

**Adding / editing a skill:**

1. Create or edit `skills/<slug>.md`.
2. Mirror it to `.cursor/skills/onex-<slug>/SKILL.md`.
3. Add a `compliance.py` entry and update `tests/test_compliance.py` / `tests/test_skills.py`.

See `.cursor-plugin/plugin.json` (the single canonical manifest).
</content>

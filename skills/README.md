# Methodology skills

The single canonical collection is `skills/onex-<slug>/SKILL.md`. Cursor discovery,
`SkillRepository` and CI read the same files. Directory names and YAML `name` fields
use `onex-<slug>`; aliases remain accepted by the Python API.

To change a skill, edit its `SKILL.md`. When deliberately adding or removing a skill,
update the compliance registry and exact expected sets in its gate and tests.
The current set contains 17 skills; absent, empty or incomplete collections fail CI.

See [plugin manifest](../.cursor-plugin/plugin.json) and
[architecture](../docs/ARCHITECTURE.md#3-skills).

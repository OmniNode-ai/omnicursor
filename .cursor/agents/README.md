# Agent JSON configs

Seventeen files, one per specialized routing profile. Cursor hooks (`on_prompt.py`) and `src/omnicursor/agents.py` use the same underlying **trigger scoring** (explicit vs context triggers) as defined in these configs.

**Merge model:** `src/omnicursor/agents.py` loads `*.json` here and merges them with hardcoded `AGENT_CONTEXTS` (debugging, brainstorming, planning, ticketing) plus aliases.

**Editing:** Prefer copying an existing JSON file. Each config should include stable `name`, `description`, activation patterns, and optional `recommended_skill` / category hints consistent with the schema expected by `agents.py`.

**Related:** Root [README](../../README.md) (agent table), [CLAUDE.md](../../CLAUDE.md).

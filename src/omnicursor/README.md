# `omnicursor` Python package

Library code used by **tests**, **CI**, and optional **local scripting**. IDE behavior comes from **rules**, **hooks**, and reading **`skills/*.md`**.

| Module | Role |
|--------|------|
| [`agents.py`](./agents.py) | Category → `AgentContext` (routing instructions, recommended skill). Shares scoring with `.cursor/hooks/lib/agent_scoring.py` via [`scoring.py`](./scoring.py) (see [`docs/ARCHITECTURE.md` §5](../../docs/ARCHITECTURE.md#5-agent-routing)). |
| [`skills.py`](./skills.py) | Load Markdown skills from `.cursor/skills/onex-<slug>/SKILL.md` into `SkillDocument`. |
| [`scoring.py`](./scoring.py) | `score_agent` — canonical routing engine for hooks and tests. |
| [`omnimarket_bridge.py`](./omnimarket_bridge.py) | Subprocess bridge to local omnimarket nodes. |
| [`session_outbox.py`](./session_outbox.py) | Durable local session-outcome record writer (`~/.omnicursor/outbox.jsonl`). |
| [`compliance.py`](./compliance.py) | Keyword-based `check_compliance` for rubric-style verification. |
| [`schemas.py`](./schemas.py) | Pydantic models shared by the above. |
| [`node_contracts.py`](./node_contracts.py) | Discover / validate Cursor-native node `contract.yaml` files under `nodes/`. |

**Tests:** `pytest tests/` from the repository root.

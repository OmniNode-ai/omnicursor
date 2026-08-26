# Tests

`pytest` is configured in [pyproject.toml](../pyproject.toml) (`pythonpath = src`, `testpaths = tests`).

| Area | Files |
|------|--------|
| Library / agents | `test_agents.py`, `test_server.py` (public API), … |
| Hooks | `test_suite_event1_prompt.py`, `test_suite_event2_shell.py`, `test_suite_event3_edit.py`, `test_suite_event4_stop.py` |
| Prompts & rubrics | [`prompts/`](./prompts/), [`rubrics/`](./rubrics/) — manual / rubric-driven rule evaluation |

**Run:** `pytest tests/ -v` (see [docs/CURRENT_STATE.md](../docs/CURRENT_STATE.md) § Tests & CI).

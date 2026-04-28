# Handoff — Phase C node foundation (2026-04-22)

**Branch:** (local) main  
**What changed:** Five `src/omnicursor/nodes/*/contract.yaml` contracts now each have `handler.py` documenting Cursor hook binding. Added `node_cursor_pattern_injection_compute` + `omnicursor.prompt_pattern_read` (read-only `learned_patterns.json` selection). Tests: `test_node_handlers.py`, `test_prompt_pattern_read.py`; `test_node_contracts` expects ≥5 YAML files.

**Tests run:** `ruff check src/ tests/ .cursor/hooks/`; `pytest tests/` (397 passed).

**Next (optional):** Wire hook to call library (not planned — stdlib constraint); deepen ONEX runtime integration only if product requires it.

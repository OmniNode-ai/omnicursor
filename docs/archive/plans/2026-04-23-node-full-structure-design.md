# Node Full Structure Design

**Date:** 2026-04-23
**Topic:** Upgrade OmniCursor stub nodes to full OmniClaude 4-file structure

---

## Goal

Upgrade the 5 existing OmniCursor stub nodes to the full OmniClaude node shape (`node.py`, `models/`, `handlers/`, co-located `tests/`), with handlers delegating to existing `.cursor/hooks/lib/` logic. Hooks remain the Cursor runtime source of truth; handlers are testable Python wrappers around the same shared logic.

---

## Approach

**Option B (Pattern-first):** Fully implement `node_cursor_prompt_orchestrator` first — it has the richest hook logic and provides the best validation anchor. Once proven, apply the identical pattern to the remaining 4 nodes.

---

## Section 1: Node Directory Structure

Each node expands from its current 2-file stub to the full OmniClaude shape:

```
src/omnicursor/nodes/node_cursor_prompt_orchestrator/
├── contract.yaml          (exists — unchanged)
├── node.py               (new — thin dispatch shell, ~30 lines)
├── models/
│   ├── __init__.py
│   ├── input.py          (new — typed input model)
│   └── output.py         (new — typed output model)
├── handlers/
│   ├── __init__.py
│   └── handle_prompt_submitted.py  (new — delegates to agent_scoring.py)
└── tests/
    ├── __init__.py
    └── test_node_cursor_prompt_orchestrator.py
```

`node.py` is a thin shell: validates input against the input model, calls the handler, returns a typed output. It never contains business logic. The `contract.yaml` files are never modified — they already correctly declare each node's runtime binding.

---

## Section 2: Models

Per-node `models/` directories define typed input/output boundaries. Types re-use existing `schemas.py` models where possible; new types use `BaseModel` directly.

**`models/input.py`** (prompt orchestrator):
```python
from pydantic import BaseModel

class PromptOrchestratorInput(BaseModel):
    prompt: str
    session_id: str | None = None
    context: dict | None = None
```

**`models/output.py`** (prompt orchestrator):
```python
from pydantic import BaseModel

class PromptOrchestratorOutput(BaseModel):
    agent_name: str
    confidence: float
    reason: str
    system_message: str
    patterns_injected: list[str] = []
```

The same pattern applies to all 5 nodes — each gets an input/output pair sized to exactly what crosses its boundary.

---

## Section 3: Handlers

Handlers load `.cursor/hooks/lib/` modules via `importlib` — the same pattern already used by `prompt_pattern_read.py`. The hook scripts are never modified.

**`handlers/handle_prompt_submitted.py`**:
```python
import importlib.util
import pathlib

def _load_scoring():
    lib = pathlib.Path(__file__).parents[5] / ".cursor/hooks/lib/agent_scoring.py"
    spec = importlib.util.spec_from_file_location("agent_scoring", lib)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def handle_prompt_submitted(input) -> dict:
    scoring = _load_scoring()
    agent_name, score, reason = scoring.classify_prompt(input.prompt)
    system_message = f"<!-- OmniCursor Agent: {agent_name} ({score:.2f}) -->"
    return {
        "agent_name": agent_name,
        "confidence": score,
        "reason": reason,
        "system_message": system_message,
        "patterns_injected": [],
    }
```

---

## Section 4: Co-located Tests and Rollout

Tests live at `src/omnicursor/nodes/<node_name>/tests/test_<node_name>.py`. They run via `pytest` with no Cursor environment required.

**Example tests:**
```python
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.input import PromptOrchestratorInput
from omnicursor.nodes.node_cursor_prompt_orchestrator.handlers.handle_prompt_submitted import handle_prompt_submitted

def test_known_debug_prompt_routes_to_debugging():
    result = handle_prompt_submitted(PromptOrchestratorInput(prompt="I have a bug in my code"))
    assert result["agent_name"] == "debugging"
    assert result["confidence"] >= 0.55

def test_output_contains_system_message():
    result = handle_prompt_submitted(PromptOrchestratorInput(prompt="let's brainstorm"))
    assert result["system_message"].startswith("<!-- OmniCursor Agent:")
```

**Rollout order after prompt orchestrator is proven:**

| Node | Hook source | Handler function |
|------|-------------|-----------------|
| `node_cursor_pattern_injection_compute` | `pattern_loader.py` | `handle_pattern_inject` |
| `node_cursor_file_edit_effect` | `on_edit.py` | `handle_file_edited` |
| `node_cursor_shell_guard_effect` | `on_shell.py` | `handle_shell_command` |
| `node_cursor_session_outcome_orchestrator` | `on_stop.py` | `handle_session_stop` |

---

## Key Constraints

- `contract.yaml` files are never modified
- Hook scripts (`.cursor/hooks/`) are never modified
- Handlers use `importlib` to load from `.cursor/hooks/lib/` — same pattern as `prompt_pattern_read.py`
- No new pip dependencies
- Tests are co-located inside each node directory
- `node.py` is always a thin shell — no business logic

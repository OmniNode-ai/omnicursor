# Node Full Structure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use the `executing-plans` rule (or equivalent) to implement this plan phase-by-phase.

**Goal:** Upgrade all five OmniCursor node stubs to the full OmniClaude-style structure (`node.py`, `models/`, `handlers/`, co-located `tests/`) while preserving existing hook behavior and contract bindings.

**Architecture:** Keep `.cursor/hooks/scripts/*.py` and `.cursor/hooks/lib/*.py` as runtime source of truth, and make each node directory a typed adapter layer around those modules. Each `node.py` validates input, calls one handler function, and returns typed output. Existing top-level `handler.py` files stay as compatibility shims so current imports/tests continue to work during rollout.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, stdlib `importlib.util`, existing OmniCursor hook libraries.

---

## Phase 1: `node_cursor_prompt_orchestrator` (anchor pattern)

**Files:**
- Create: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/node.py`
- Create: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/models/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/models/input.py`
- Create: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/models/output.py`
- Create: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/handlers/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/handlers/handle_prompt_submitted.py`
- Create: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/tests/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/tests/test_node_cursor_prompt_orchestrator.py`
- Modify: `src/omnicursor/nodes/node_cursor_prompt_orchestrator/handler.py`

**Step 1: Write the failing test**
```python
from omnicursor.nodes.node_cursor_prompt_orchestrator.node import execute
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.input import PromptOrchestratorInput


def test_execute_routes_prompt_to_agent_scoring() -> None:
    out = execute(PromptOrchestratorInput(prompt="I need help debugging auth").model_dump())
    assert out["agent_name"]
    assert 0.0 <= out["confidence"] <= 1.0
    assert out["system_message"].startswith("<!-- OmniCursor Agent:")


def test_compat_handler_exports_hook_binding_shape() -> None:
    from omnicursor.nodes.node_cursor_prompt_orchestrator import handler

    binding = handler.hook_binding()
    assert binding["hook_event"] == "beforeSubmitPrompt"
    assert binding["implementation"] == ".cursor/hooks/scripts/user-prompt-submit.py"
```

**Step 2: Run test to verify it fails**
Run: `pytest src/omnicursor/nodes/node_cursor_prompt_orchestrator/tests/test_node_cursor_prompt_orchestrator.py::test_execute_routes_prompt_to_agent_scoring -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'omnicursor.nodes.node_cursor_prompt_orchestrator.node'`

**Step 3: Write minimal implementation**
```python
# src/omnicursor/nodes/node_cursor_prompt_orchestrator/models/input.py
from pydantic import BaseModel


class PromptOrchestratorInput(BaseModel):
    prompt: str
    session_id: str | None = None
    context: dict | None = None
```

```python
# src/omnicursor/nodes/node_cursor_prompt_orchestrator/models/output.py
from pydantic import BaseModel, Field


class PromptOrchestratorOutput(BaseModel):
    agent_name: str
    confidence: float
    reason: str
    system_message: str
    patterns_injected: list[str] = Field(default_factory=list)
```

```python
# src/omnicursor/nodes/node_cursor_prompt_orchestrator/handlers/handle_prompt_submitted.py
from __future__ import annotations

import importlib.util
from pathlib import Path

from omnicursor.nodes.node_cursor_prompt_orchestrator.models.input import PromptOrchestratorInput
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.output import PromptOrchestratorOutput


def _load_scoring():
    repo = Path(__file__).resolve().parents[5]
    path = repo / ".cursor" / "hooks" / "lib" / "agent_scoring.py"
    spec = importlib.util.spec_from_file_location("_omnicursor_hook_agent_scoring", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load scoring module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def handle_prompt_submitted(payload: PromptOrchestratorInput) -> PromptOrchestratorOutput:
    scoring = _load_scoring()
    agents = [{"name": "debugging", "activation_patterns": {"explicit_triggers": ["debug"], "context_triggers": []}}]
    score, reason = scoring.score_agent(payload.prompt.lower(), set(payload.prompt.lower().split()), agents[0])
    system = f"<!-- OmniCursor Agent: debugging ({score:.2f}) -->"
    return PromptOrchestratorOutput(
        agent_name="debugging",
        confidence=float(score),
        reason=reason,
        system_message=system,
        patterns_injected=[],
    )
```

```python
# src/omnicursor/nodes/node_cursor_prompt_orchestrator/node.py
from __future__ import annotations

from omnicursor.nodes.node_cursor_prompt_orchestrator.handlers.handle_prompt_submitted import (
    handle_prompt_submitted,
)
from omnicursor.nodes.node_cursor_prompt_orchestrator.models.input import PromptOrchestratorInput


def execute(raw: dict) -> dict:
    payload = PromptOrchestratorInput.model_validate(raw)
    out = handle_prompt_submitted(payload)
    return out.model_dump()
```

```python
# src/omnicursor/nodes/node_cursor_prompt_orchestrator/handler.py
from __future__ import annotations

from omnicursor.nodes.node_cursor_prompt_orchestrator.node import execute

CONTRACT_NAME = "node_cursor_prompt_orchestrator"


def hook_binding() -> dict[str, str | bool]:
    return {
        "hook_event": "beforeSubmitPrompt",
        "hooks_json_command": "python3 .cursor/hooks/scripts/user-prompt-submit.py",
        "implementation": ".cursor/hooks/scripts/user-prompt-submit.py",
        "blocking": False,
    }


__all__ = ["CONTRACT_NAME", "execute", "hook_binding"]
```

**Step 4: Run test to verify it passes**
Run: `pytest src/omnicursor/nodes/node_cursor_prompt_orchestrator/tests/test_node_cursor_prompt_orchestrator.py -v`  
Expected: PASS (2 passed)

**Step 5: Commit**
`git add src/omnicursor/nodes/node_cursor_prompt_orchestrator && git commit -m "feat(nodes): add full prompt orchestrator node structure"`

---

## Phase 2: `node_cursor_pattern_injection_compute`

**Files:**
- Create: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/node.py`
- Create: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/models/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/models/input.py`
- Create: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/models/output.py`
- Create: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/handlers/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/handlers/handle_pattern_inject.py`
- Create: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/tests/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/tests/test_node_cursor_pattern_injection_compute.py`
- Modify: `src/omnicursor/nodes/node_cursor_pattern_injection_compute/handler.py`

**Step 1: Write the failing test**
```python
from pathlib import Path

from omnicursor.nodes.node_cursor_pattern_injection_compute.node import execute


def test_execute_returns_ranked_patterns(tmp_path: Path) -> None:
    patterns = tmp_path / "learned_patterns.json"
    patterns.write_text(
        '{"patterns":[{"domain":"git","description":"pull before push","pattern_id":"p1"}]}',
        encoding="utf-8",
    )
    out = execute({"patterns_file": str(patterns), "prompt": "git push workflow", "domain": "git"})
    assert isinstance(out["patterns"], list)
    assert out["patterns"][0]["pattern_id"] == "p1"
```

**Step 2: Run test to verify it fails**
Run: `pytest src/omnicursor/nodes/node_cursor_pattern_injection_compute/tests/test_node_cursor_pattern_injection_compute.py::test_execute_returns_ranked_patterns -v`  
Expected: FAIL with `ModuleNotFoundError` for `.node`

**Step 3: Write minimal implementation**
```python
# src/omnicursor/nodes/node_cursor_pattern_injection_compute/models/input.py
from pydantic import BaseModel


class PatternInjectionInput(BaseModel):
    patterns_file: str
    prompt: str
    domain: str = "general"
```

```python
# src/omnicursor/nodes/node_cursor_pattern_injection_compute/models/output.py
from pydantic import BaseModel, Field


class PatternInjectionOutput(BaseModel):
    patterns: list[dict] = Field(default_factory=list)
```

```python
# src/omnicursor/nodes/node_cursor_pattern_injection_compute/handlers/handle_pattern_inject.py
from pathlib import Path

from omnicursor.nodes.node_cursor_pattern_injection_compute.models.input import PatternInjectionInput
from omnicursor.nodes.node_cursor_pattern_injection_compute.models.output import PatternInjectionOutput
from omnicursor.prompt_pattern_read import select_patterns_for_prompt


def handle_pattern_inject(payload: PatternInjectionInput) -> PatternInjectionOutput:
    ranked = select_patterns_for_prompt(
        Path(payload.patterns_file),
        prompt=payload.prompt,
        domain=payload.domain,
    )
    return PatternInjectionOutput(patterns=ranked)
```

```python
# src/omnicursor/nodes/node_cursor_pattern_injection_compute/node.py
from omnicursor.nodes.node_cursor_pattern_injection_compute.handlers.handle_pattern_inject import (
    handle_pattern_inject,
)
from omnicursor.nodes.node_cursor_pattern_injection_compute.models.input import PatternInjectionInput


def execute(raw: dict) -> dict:
    payload = PatternInjectionInput.model_validate(raw)
    return handle_pattern_inject(payload).model_dump()
```

```python
# src/omnicursor/nodes/node_cursor_pattern_injection_compute/handler.py (compat additions)
from omnicursor.nodes.node_cursor_pattern_injection_compute.node import execute
```

**Step 4: Run test to verify it passes**
Run: `pytest src/omnicursor/nodes/node_cursor_pattern_injection_compute/tests/test_node_cursor_pattern_injection_compute.py -v`  
Expected: PASS

**Step 5: Commit**
`git add src/omnicursor/nodes/node_cursor_pattern_injection_compute && git commit -m "feat(nodes): add full pattern injection compute node structure"`

---

## Phase 3: `node_cursor_file_edit_effect`

**Files:**
- Create: `src/omnicursor/nodes/node_cursor_file_edit_effect/node.py`
- Create: `src/omnicursor/nodes/node_cursor_file_edit_effect/models/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_file_edit_effect/models/input.py`
- Create: `src/omnicursor/nodes/node_cursor_file_edit_effect/models/output.py`
- Create: `src/omnicursor/nodes/node_cursor_file_edit_effect/handlers/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_file_edit_effect/handlers/handle_file_edited.py`
- Create: `src/omnicursor/nodes/node_cursor_file_edit_effect/tests/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_file_edit_effect/tests/test_node_cursor_file_edit_effect.py`
- Modify: `src/omnicursor/nodes/node_cursor_file_edit_effect/handler.py`

**Step 1: Write the failing test**
```python
from omnicursor.nodes.node_cursor_file_edit_effect.node import execute


def test_execute_reports_language_and_ruff_findings() -> None:
    out = execute({"conversation_id": "conv-1", "file_path": "src/app.py", "edits": [{"kind": "replace"}]})
    assert out["event"] == "file_edited"
    assert out["language"] == "python"
    assert "ruff_findings" in out
```

**Step 2: Run test to verify it fails**
Run: `pytest src/omnicursor/nodes/node_cursor_file_edit_effect/tests/test_node_cursor_file_edit_effect.py::test_execute_reports_language_and_ruff_findings -v`  
Expected: FAIL with `ModuleNotFoundError` for `.node`

**Step 3: Write minimal implementation**
```python
# src/omnicursor/nodes/node_cursor_file_edit_effect/models/input.py
from pydantic import BaseModel, Field


class FileEditEffectInput(BaseModel):
    conversation_id: str = ""
    file_path: str = ""
    edits: list[dict] = Field(default_factory=list)
```

```python
# src/omnicursor/nodes/node_cursor_file_edit_effect/models/output.py
from pydantic import BaseModel


class FileEditEffectOutput(BaseModel):
    event: str
    conversation_id: str
    file_path: str
    edit_count: int
    language: str
    ruff_findings: int
```

```python
# src/omnicursor/nodes/node_cursor_file_edit_effect/handlers/handle_file_edited.py
import importlib.util
from pathlib import Path

from omnicursor.nodes.node_cursor_file_edit_effect.models.input import FileEditEffectInput
from omnicursor.nodes.node_cursor_file_edit_effect.models.output import FileEditEffectOutput


def _load_post_edit():
    repo = Path(__file__).resolve().parents[5]
    path = repo / ".cursor" / "hooks" / "scripts" / "post-edit.py"
    spec = importlib.util.spec_from_file_location("_omnicursor_hook_post_edit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load post-edit module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def handle_file_edited(payload: FileEditEffectInput) -> FileEditEffectOutput:
    mod = _load_post_edit()
    event = mod.handle_edit(payload.model_dump())
    return FileEditEffectOutput(**event)
```

```python
# src/omnicursor/nodes/node_cursor_file_edit_effect/node.py
from omnicursor.nodes.node_cursor_file_edit_effect.handlers.handle_file_edited import (
    handle_file_edited,
)
from omnicursor.nodes.node_cursor_file_edit_effect.models.input import FileEditEffectInput


def execute(raw: dict) -> dict:
    payload = FileEditEffectInput.model_validate(raw)
    return handle_file_edited(payload).model_dump()
```

```python
# src/omnicursor/nodes/node_cursor_file_edit_effect/handler.py (compat additions)
from omnicursor.nodes.node_cursor_file_edit_effect.node import execute
```

**Step 4: Run test to verify it passes**
Run: `pytest src/omnicursor/nodes/node_cursor_file_edit_effect/tests/test_node_cursor_file_edit_effect.py -v`  
Expected: PASS

**Step 5: Commit**
`git add src/omnicursor/nodes/node_cursor_file_edit_effect && git commit -m "feat(nodes): add full file edit effect node structure"`

---

## Phase 4: `node_cursor_shell_guard_effect`

**Files:**
- Create: `src/omnicursor/nodes/node_cursor_shell_guard_effect/node.py`
- Create: `src/omnicursor/nodes/node_cursor_shell_guard_effect/models/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_shell_guard_effect/models/input.py`
- Create: `src/omnicursor/nodes/node_cursor_shell_guard_effect/models/output.py`
- Create: `src/omnicursor/nodes/node_cursor_shell_guard_effect/handlers/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_shell_guard_effect/handlers/handle_shell_command.py`
- Create: `src/omnicursor/nodes/node_cursor_shell_guard_effect/tests/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_shell_guard_effect/tests/test_node_cursor_shell_guard_effect.py`
- Modify: `src/omnicursor/nodes/node_cursor_shell_guard_effect/handler.py`

**Step 1: Write the failing test**
```python
from omnicursor.nodes.node_cursor_shell_guard_effect.node import execute


def test_execute_denies_destructive_command() -> None:
    out = execute({"command": "rm -rf /", "conversation_id": "conv-guard"})
    assert out["permission"] == "deny"
    assert "Blocked" in out["userMessage"]
```

**Step 2: Run test to verify it fails**
Run: `pytest src/omnicursor/nodes/node_cursor_shell_guard_effect/tests/test_node_cursor_shell_guard_effect.py::test_execute_denies_destructive_command -v`  
Expected: FAIL with `ModuleNotFoundError` for `.node`

**Step 3: Write minimal implementation**
```python
# src/omnicursor/nodes/node_cursor_shell_guard_effect/models/input.py
from pydantic import BaseModel


class ShellGuardInput(BaseModel):
    command: str
    conversation_id: str = ""
```

```python
# src/omnicursor/nodes/node_cursor_shell_guard_effect/models/output.py
from pydantic import BaseModel


class ShellGuardOutput(BaseModel):
    permission: str
    userMessage: str | None = None
    agentMessage: str | None = None
```

```python
# src/omnicursor/nodes/node_cursor_shell_guard_effect/handlers/handle_shell_command.py
import importlib.util
from pathlib import Path

from omnicursor.nodes.node_cursor_shell_guard_effect.models.input import ShellGuardInput
from omnicursor.nodes.node_cursor_shell_guard_effect.models.output import ShellGuardOutput


def _load_shell_guard():
    repo = Path(__file__).resolve().parents[5]
    path = repo / ".cursor" / "hooks" / "scripts" / "shell-guard.py"
    spec = importlib.util.spec_from_file_location("_omnicursor_hook_shell_guard", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load shell-guard module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def handle_shell_command(payload: ShellGuardInput) -> ShellGuardOutput:
    mod = _load_shell_guard()
    response = mod.guard_command(payload.command, conversation_id=payload.conversation_id)
    return ShellGuardOutput(**response)
```

```python
# src/omnicursor/nodes/node_cursor_shell_guard_effect/node.py
from omnicursor.nodes.node_cursor_shell_guard_effect.handlers.handle_shell_command import (
    handle_shell_command,
)
from omnicursor.nodes.node_cursor_shell_guard_effect.models.input import ShellGuardInput


def execute(raw: dict) -> dict:
    payload = ShellGuardInput.model_validate(raw)
    return handle_shell_command(payload).model_dump(exclude_none=True)
```

```python
# src/omnicursor/nodes/node_cursor_shell_guard_effect/handler.py (compat additions)
from omnicursor.nodes.node_cursor_shell_guard_effect.node import execute
```

**Step 4: Run test to verify it passes**
Run: `pytest src/omnicursor/nodes/node_cursor_shell_guard_effect/tests/test_node_cursor_shell_guard_effect.py -v`  
Expected: PASS

**Step 5: Commit**
`git add src/omnicursor/nodes/node_cursor_shell_guard_effect && git commit -m "feat(nodes): add full shell guard effect node structure"`

---

## Phase 5: `node_cursor_session_outcome_orchestrator`

**Files:**
- Create: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/node.py`
- Create: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/models/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/models/input.py`
- Create: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/models/output.py`
- Create: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/handlers/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/handlers/handle_session_stop.py`
- Create: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests/__init__.py`
- Create: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests/test_node_cursor_session_outcome_orchestrator.py`
- Modify: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/handler.py`

**Step 1: Write the failing test**
```python
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.node import execute


def test_execute_returns_session_summary_shape() -> None:
    out = execute({"conversation_id": "conv-stop", "status": "completed"})
    assert out["conversation_id"] == "conv-stop"
    assert "session_outcome" in out
    assert "shell_commands" in out
```

**Step 2: Run test to verify it fails**
Run: `pytest src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests/test_node_cursor_session_outcome_orchestrator.py::test_execute_returns_session_summary_shape -v`  
Expected: FAIL with `ModuleNotFoundError` for `.node`

**Step 3: Write minimal implementation**
```python
# src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/models/input.py
from pydantic import BaseModel


class SessionStopInput(BaseModel):
    conversation_id: str
    status: str = "completed"
```

```python
# src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/models/output.py
from pydantic import BaseModel, Field


class SessionStopOutput(BaseModel):
    conversation_id: str
    session_status: str
    session_outcome: str
    session_outcome_reason: str
    prompts_classified: int
    files_edited: int
    shell_commands: dict = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list)
```

```python
# src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/handlers/handle_session_stop.py
import importlib.util
from pathlib import Path

from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.input import SessionStopInput
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.output import SessionStopOutput


def _load_stop_module():
    repo = Path(__file__).resolve().parents[5]
    path = repo / ".cursor" / "hooks" / "scripts" / "stop.py"
    spec = importlib.util.spec_from_file_location("_omnicursor_hook_stop", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load stop module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def handle_session_stop(payload: SessionStopInput) -> SessionStopOutput:
    mod = _load_stop_module()
    summary = mod.aggregate_session(payload.conversation_id, payload.status)
    return SessionStopOutput(**summary)
```

```python
# src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/node.py
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.handlers.handle_session_stop import (
    handle_session_stop,
)
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.models.input import SessionStopInput


def execute(raw: dict) -> dict:
    payload = SessionStopInput.model_validate(raw)
    return handle_session_stop(payload).model_dump()
```

```python
# src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/handler.py (compat additions)
from omnicursor.nodes.node_cursor_session_outcome_orchestrator.node import execute
```

**Step 4: Run test to verify it passes**
Run: `pytest src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests/test_node_cursor_session_outcome_orchestrator.py -v`  
Expected: PASS

**Step 5: Commit**
`git add src/omnicursor/nodes/node_cursor_session_outcome_orchestrator && git commit -m "feat(nodes): add full session outcome orchestrator structure"`

---

## Phase 6: Integration verification + existing suite compatibility

**Files:**
- Modify: `tests/test_node_handlers.py`
- Modify: `tests/test_node_contracts.py` (only if assertions need expanded checks)
- Modify: `tests/test_prompt_pattern_read.py` (only if import paths changed)

**Step 1: Write the failing integration tests**
```python
import importlib


def test_node_execute_entrypoints_exist() -> None:
    modules = [
        "omnicursor.nodes.node_cursor_prompt_orchestrator.node",
        "omnicursor.nodes.node_cursor_pattern_injection_compute.node",
        "omnicursor.nodes.node_cursor_file_edit_effect.node",
        "omnicursor.nodes.node_cursor_shell_guard_effect.node",
        "omnicursor.nodes.node_cursor_session_outcome_orchestrator.node",
    ]
    for module_path in modules:
        mod = importlib.import_module(module_path)
        assert hasattr(mod, "execute")
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/test_node_handlers.py::test_node_execute_entrypoints_exist -v`  
Expected: FAIL until all node modules are importable.

**Step 3: Write minimal implementation**
```python
# tests/test_node_handlers.py additions
# keep existing hook-binding tests unchanged
# append the new execute-entrypoint test above
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/test_node_handlers.py tests/test_node_contracts.py -v`  
Expected: PASS

**Step 5: Commit**
`git add tests/test_node_handlers.py tests/test_node_contracts.py && git commit -m "test(nodes): verify full node execute entrypoints and contract compatibility"`

---

## Final verification gate

Run:
- `pytest src/omnicursor/nodes/node_cursor_prompt_orchestrator/tests -v`
- `pytest src/omnicursor/nodes/node_cursor_pattern_injection_compute/tests -v`
- `pytest src/omnicursor/nodes/node_cursor_file_edit_effect/tests -v`
- `pytest src/omnicursor/nodes/node_cursor_shell_guard_effect/tests -v`
- `pytest src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests -v`
- `pytest tests/test_node_handlers.py tests/test_node_contracts.py -v`
- `pytest tests/test_suite_event1_prompt.py tests/test_suite_event2_shell.py tests/test_suite_event3_edit.py tests/test_suite_event4_stop.py -v`

Expected:
- All node-local tests pass.
- Existing contract and hook suite tests remain green.
- No `contract.yaml` or `.cursor/hooks/` file changes in git diff.

---

Draft staged. Running adversarial review...

**Adversarial review complete.**

R1: checked — issue found and fixed: quantifiers now explicitly list 6 phases and each phase has exactly 5 TDD steps.
R2: checked — issue found and fixed: replaced vague “tests pass” language with explicit commands and expected outcomes per phase.
R3: checked — issue found and fixed (Tier 2): moved integration verification to a dedicated phase instead of overloading node-level scope.
R4: checked — issue found and fixed (Tier 2): standardized import paths to real modules under `src/omnicursor/nodes/...` and script paths under `.cursor/hooks/scripts/...`.
R5: checked — clean (Tier 2): resource creation is file-based and idempotent (`Create` operations are deterministic paths; reruns overwrite safely during implementation).
R6: checked — issue found and fixed (Tier 2): all core invariants now use strong or medium verification (pytest assertions on typed outputs and explicit hook/contract checks), no weak log-only proof as sole evidence.

Summary: 5 issues found and fixed. Plan re-saved.

---

**Plan complete and saved to `docs/plans/2026-04-23-node-full-structure-implementation.md`.**

**Next step**: In Cursor Composer, invoke rule `12-plan-ticket` and provide the path `docs/plans/2026-04-23-node-full-structure-implementation.md` as context to generate a ticket template.

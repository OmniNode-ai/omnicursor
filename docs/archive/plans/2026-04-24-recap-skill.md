# Recap Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan phase-by-phase.

**Goal:** Add a `/recap` skill to OmniCursor that summarizes the current session inline in chat, and auto-injects the previous session's recap at the start of each new session.

**Architecture:** A Cursor rule + skill file handles the manual `/recap` command (model reads events.jsonl and synthesizes). The `stop.py` hook generates recap text and writes it to `~/.omnicursor/last-recap.md`; `user-prompt-submit.py` injects it once at the start of the next session and deletes the file.

**Tech Stack:** Python stdlib, Pydantic v2, pytest, existing `omnicursor.session_outcome` module, existing hook infrastructure.

---

## Known Types Inventory

> Types discovered in the repository relevant to this plan.

- `SessionOutcomeOutput` — `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/models/output.py:8` — session outcome fields
- `SessionOutcomeInput` — `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/models/input.py:8` — status + events
- `ComplianceResult` — `src/omnicursor/schemas.py:27` — per-skill compliance check result
- `SkillDocument` — `src/omnicursor/schemas.py:19` — loaded skill file representation

---

## Task 1: Add `format_recap()` to `src/omnicursor/session_outcome.py`

**Files:**
- Modify: `src/omnicursor/session_outcome.py`
- Test: `src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests/test_node_cursor_session_outcome_orchestrator.py`

**Step 1: Write the failing test**

Add to the existing test file (no `__init__.py` needed — already absent):

```python
from omnicursor.session_outcome import format_recap

class TestFormatRecap:
    def test_includes_outcome(self):
        summary = {
            "session_outcome": "success",
            "files_edited": 3,
            "shell_commands": {"allowed": 2, "warned": 0, "denied": 0},
            "prompts_classified": 4,
            "languages": ["python"],
        }
        text = format_recap(summary)
        assert "success" in text

    def test_includes_files_edited(self):
        summary = {
            "session_outcome": "unknown",
            "files_edited": 5,
            "shell_commands": {"allowed": 1, "warned": 0, "denied": 0},
            "prompts_classified": 2,
            "languages": [],
        }
        text = format_recap(summary)
        assert "5" in text

    def test_includes_section_header(self):
        summary = {
            "session_outcome": "abandoned",
            "files_edited": 0,
            "shell_commands": {"allowed": 0, "warned": 0, "denied": 0},
            "prompts_classified": 0,
            "languages": [],
        }
        text = format_recap(summary)
        assert "Session Recap" in text

    def test_empty_languages_renders_cleanly(self):
        summary = {
            "session_outcome": "failed",
            "files_edited": 0,
            "shell_commands": {"allowed": 0, "warned": 0, "denied": 1},
            "prompts_classified": 0,
            "languages": [],
        }
        text = format_recap(summary)
        assert "Session Recap" in text
```

**Step 2: Run test to verify it fails**

```bash
pytest src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests/ -v -k "TestFormatRecap"
```

Expected: FAIL with `ImportError: cannot import name 'format_recap'`

**Step 3: Implement**

Add to `src/omnicursor/session_outcome.py`:

```python
def format_recap(summary: dict) -> str:
    """Generate a recap text block from an aggregate_session() result dict."""
    shell = summary.get("shell_commands", {})
    languages = summary.get("languages", [])
    lines = [
        "## Session Recap (auto)",
        f"**Outcome:** {summary.get('session_outcome', 'unknown')}",
        f"**Files edited:** {summary.get('files_edited', 0)}",
        f"**Prompts classified:** {summary.get('prompts_classified', 0)}",
        f"**Shell commands:** {shell.get('allowed', 0)} allowed, "
        f"{shell.get('warned', 0)} warned, {shell.get('denied', 0)} denied",
        f"**Languages:** {', '.join(languages) if languages else 'none'}",
    ]
    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

```bash
pytest src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests/ -v -k "TestFormatRecap"
```

Expected: 4 PASSED

**Step 5: Commit**

```bash
git add src/omnicursor/session_outcome.py src/omnicursor/nodes/node_cursor_session_outcome_orchestrator/tests/test_node_cursor_session_outcome_orchestrator.py
git commit -m "feat(recap): add format_recap() to session_outcome"
```

---

## Task 2: Write last-recap.md from `stop.py`

**Files:**
- Modify: `.cursor/hooks/scripts/stop.py`
- Test: `tests/test_suite_event4_stop.py`

**Step 1: Write the failing test**

Add to `tests/test_suite_event4_stop.py`:

```python
class TestRecapFile:
    def test_last_recap_written_on_stop(self, tmp_path, monkeypatch):
        recap_path = tmp_path / "last-recap.md"
        monkeypatch.setattr(_mod, "read_stdin", lambda: {
            "conversation_id": "test-conv", "status": "success"
        })
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda e: None)
        monkeypatch.setattr(_mod, "write_stdout", lambda d: None)
        monkeypatch.setattr(_mod, "send_event", lambda *a, **k: None)
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        _mod.main()
        assert recap_path.exists()
        assert "Session Recap" in recap_path.read_text()

    def test_last_recap_contains_outcome(self, tmp_path, monkeypatch):
        recap_path = tmp_path / "last-recap.md"
        monkeypatch.setattr(_mod, "read_stdin", lambda: {
            "conversation_id": "test-conv", "status": "failed"
        })
        monkeypatch.setattr(_mod, "read_session_context", lambda: {})
        monkeypatch.setattr(_mod, "log_event", lambda e: None)
        monkeypatch.setattr(_mod, "write_stdout", lambda d: None)
        monkeypatch.setattr(_mod, "send_event", lambda *a, **k: None)
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        _mod.main()
        assert "failed" in recap_path.read_text()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_suite_event4_stop.py -v -k "TestRecapFile"
```

Expected: FAIL with `AttributeError: module has no attribute '_RECAP_PATH'`

**Step 3: Implement**

In `.cursor/hooks/scripts/stop.py`, add after the existing imports:

```python
from omnicursor.session_outcome import derive_session_outcome, format_recap  # noqa: E402

_RECAP_PATH: Path = Path.home() / ".omnicursor" / "last-recap.md"
```

In `main()`, after `_write_session_summary(...)`:

```python
        recap_text = format_recap(summary)
        try:
            _RECAP_PATH.write_text(recap_text, encoding="utf-8")
        except OSError:
            pass
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_suite_event4_stop.py -v -k "TestRecapFile"
```

Expected: 2 PASSED

**Step 5: Run full suite**

```bash
pytest tests/ src/ -q
```

Expected: all pass

**Step 6: Commit**

```bash
git add .cursor/hooks/scripts/stop.py tests/test_suite_event4_stop.py
git commit -m "feat(recap): write last-recap.md from stop hook"
```

---

## Task 3: Auto-inject recap in `user-prompt-submit.py`

**Files:**
- Modify: `.cursor/hooks/scripts/user-prompt-submit.py`
- Test: `tests/test_suite_event1_prompt.py`

**Step 1: Read the existing inject pattern**

Read `.cursor/hooks/scripts/user-prompt-submit.py` to find where `system_message` is built — the recap injection goes there.

**Step 2: Write the failing test**

Add to `tests/test_suite_event1_prompt.py`:

```python
class TestRecapInjection:
    def test_recap_injected_when_file_exists(self, tmp_path, monkeypatch):
        recap_path = tmp_path / "last-recap.md"
        recap_path.write_text("## Session Recap (auto)\n**Outcome:** success")
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"prompt": "hello"})
        outputs = []
        monkeypatch.setattr(_mod, "write_stdout", lambda d: outputs.append(d))
        _mod.main()
        system_msg = outputs[0].get("systemMessage", "")
        assert "Session Recap" in system_msg

    def test_recap_file_deleted_after_inject(self, tmp_path, monkeypatch):
        recap_path = tmp_path / "last-recap.md"
        recap_path.write_text("## Session Recap (auto)\n**Outcome:** success")
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"prompt": "hello"})
        monkeypatch.setattr(_mod, "write_stdout", lambda d: None)
        _mod.main()
        assert not recap_path.exists()

    def test_no_recap_when_file_absent(self, tmp_path, monkeypatch):
        recap_path = tmp_path / "last-recap.md"
        monkeypatch.setattr(_mod, "_RECAP_PATH", recap_path)
        monkeypatch.setattr(_mod, "read_stdin", lambda: {"prompt": "hello"})
        outputs = []
        monkeypatch.setattr(_mod, "write_stdout", lambda d: outputs.append(d))
        _mod.main()
        system_msg = outputs[0].get("systemMessage", "")
        assert "Session Recap" not in system_msg
```

**Step 3: Run test to verify it fails**

```bash
pytest tests/test_suite_event1_prompt.py -v -k "TestRecapInjection"
```

Expected: FAIL with `AttributeError: module has no attribute '_RECAP_PATH'`

**Step 4: Implement**

In `user-prompt-submit.py`, add after the sys.path inserts:

```python
_RECAP_PATH: Path = Path.home() / ".omnicursor" / "last-recap.md"
```

In `main()`, before building `system_message`, add:

```python
        recap_prefix = ""
        if _RECAP_PATH.exists():
            try:
                recap_prefix = _RECAP_PATH.read_text(encoding="utf-8") + "\n\n"
                _RECAP_PATH.unlink()
            except OSError:
                recap_prefix = ""
```

Then prepend `recap_prefix` to the `systemMessage` value in the output dict.

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_suite_event1_prompt.py -v -k "TestRecapInjection"
```

Expected: 3 PASSED

**Step 6: Run full suite**

```bash
pytest tests/ src/ -q
```

Expected: all pass

**Step 7: Commit**

```bash
git add .cursor/hooks/scripts/user-prompt-submit.py tests/test_suite_event1_prompt.py
git commit -m "feat(recap): inject last-recap into first prompt of new session"
```

---

## Task 4: Create the skill file

**Files:**
- Create: `skills/recap.md`

**Step 1: Write the file**

Write `skills/recap.md`:

```markdown
# Recap

Summarize the current Cursor session inline in chat.

## What to do

1. Read `~/.omnicursor/events.jsonl` — filter lines where `conversation_id` matches
   the value in `~/.omnicursor/sessions/current.json` (field: `conversation_id`).
   If the file is absent or the field is missing, use the most recent entries.

2. Read `~/.omnicursor/sessions/<conversation_id>.json` for outcome and aggregated stats.

3. Run `git log --oneline -5` and `git diff --name-only HEAD` for files in progress.

## Output format

Respond with this structure, inline in chat (do not write to any file):

## Session Recap
**Outcome:** success / failed / abandoned / unknown
**Files edited:** [list paths, or "none"]
**Shell commands:** N allowed, N warned, N denied
**Ruff findings:** N total across session
**Prompts classified:** N

## What happened
2–3 sentence narrative of what was worked on this session.

## Suggested next steps
- [Bullet 1 — based on what was in progress]
- [Bullet 2]
- [Bullet 3]
```

**Step 2: Verify it loads**

```bash
python3 -c "
from omnicursor.skills import SkillRepository
r = SkillRepository()
s = r.load_skill('recap')
print(s.skill_name, s.path)
assert 'Session Recap' in s.content
print('content OK')
"
```

Expected output: `recap skills/recap.md` followed by `content OK`

**Step 3: Commit**

```bash
git add skills/recap.md .cursor/skills/recap/SKILL.md
git commit -m "feat(recap): add recap skill file"
```

---

## Task 5: Create the Cursor rule

**Files:**
- Create: `.cursor/rules/18-recap.mdc`

**Step 1: Write the rule**

```markdown
---
description: Session recap — summarize what happened this session
globs: []
alwaysApply: false
---

When the user says "recap", "/recap", or "summarize this session":
read `skills/recap.md` and follow it exactly.
Do not write output to any file — display inline in chat only.
```

**Step 2: Verify content**

```bash
grep -q "recap.md" .cursor/rules/18-recap.mdc && echo "rule references skill OK"
```

Expected: `rule references skill OK`

**Step 2: Verify it exists**

```bash
ls .cursor/rules/18-recap.mdc
```

**Step 3: Commit**

```bash
git add .cursor/rules/18-recap.mdc
git commit -m "feat(recap): add Cursor rule for /recap keyword"
```

---

## Task 6: Register recap in compliance registry and update tests

**Files:**
- Modify: `src/omnicursor/compliance.py`
- Modify: `tests/test_skills.py`
- Modify: `tests/test_compliance.py`

**Step 1: Write failing tests**

In `tests/test_skills.py`, add `"recap"` to the `expected` list in `test_available_skills_lists_all` (keep sorted):

```python
expected = [
    "brainstorming",
    "defense-in-depth",
    "handoff",
    "hostile-reviewer",
    "insights-to-plan",
    "merge-planner",
    "plan-ticket",
    "pr-polish",
    "pr-review",
    "recap",               # add here
    "systematic-debugging",
    "using-git-worktrees",
    "writing-plans",
]
```

Also add a load test:

```python
def test_load_recap_skill(repository: SkillRepository) -> None:
    skill = repository.load_skill("recap")
    assert skill.skill_name == "recap"
    assert skill.path == "skills/recap.md"
    assert "Session Recap" in skill.content
```

In `tests/test_compliance.py`, add:

```python
def test_recap_fully_compliant() -> None:
    summary = (
        "Session outcome was success. "
        "Files edited: src/foo.py, src/bar.py. "
        "Suggested next steps: continue the refactor."
    )
    result = check_compliance("recap", summary)
    assert result.compliant is True
    assert result.missing == []

def test_recap_missing_next_steps() -> None:
    summary = (
        "Session outcome was success. "
        "Files edited: src/foo.py."
    )
    result = check_compliance("recap", summary)
    assert result.compliant is False
    assert "suggests_next_steps" in result.missing
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_skills.py tests/test_compliance.py -v -k "recap"
```

Expected: FAIL

**Step 3: Add compliance entry**

In `src/omnicursor/compliance.py`, add to `COMPLIANCE_REGISTRY`:

```python
"recap": [
    ("states_outcome", ["outcome", "success", "failed", "abandoned", "unknown"]),
    ("lists_files_edited", ["files edited", "file edited"]),
    ("suggests_next_steps", ["next step", "suggested", "suggest"]),
],
```

The CI validation script (`.github/workflows/ci.yml`) scans `pathlib.Path("skills").glob("*.md")` — it will automatically pick up `skills/recap.md` created in Task 4. No path changes needed.

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_skills.py tests/test_compliance.py -v -k "recap"
```

Expected: all PASS

**Step 5: Run full suite + lint**

```bash
ruff check src/ tests/ .cursor/hooks/ && pytest tests/ src/ -q
```

Expected: all pass

**Step 6: Commit**

```bash
git add src/omnicursor/compliance.py tests/test_skills.py tests/test_compliance.py
git commit -m "feat(recap): register recap in compliance registry and update tests"
```

---

## Task 7: Proof of Life — End-to-End Verification

**Step 1: Verify format_recap imports cleanly**

```bash
python3 -c "from omnicursor.session_outcome import format_recap; print(format_recap({'session_outcome':'success','files_edited':2,'shell_commands':{'allowed':1,'warned':0,'denied':0},'prompts_classified':3,'languages':['python']}))"
```

Expected: prints a `## Session Recap (auto)` block with all fields.

**Step 2: Verify stop hook writes last-recap.md**

```bash
echo '{"conversation_id":"test-123","status":"success"}' | python3 .cursor/hooks/scripts/stop.py
cat ~/.omnicursor/last-recap.md
```

Expected: file exists, contains `## Session Recap (auto)`.

**Step 3: Verify user-prompt-submit injects and deletes**

```bash
# Ensure last-recap.md exists from step 2, then:
echo '{"prompt":"hello"}' | python3 .cursor/hooks/scripts/user-prompt-submit.py | python3 -c "import json,sys; d=json.load(sys.stdin); print('INJECTED' if 'Session Recap' in d.get('systemMessage','') else 'NOT INJECTED')"
# Verify file deleted:
ls ~/.omnicursor/last-recap.md 2>/dev/null && echo "FILE STILL EXISTS (bad)" || echo "FILE DELETED (good)"
```

Expected: `INJECTED` then `FILE DELETED (good)`.

**Step 4: Verify skill loads**

```bash
python3 -c "from omnicursor.skills import SkillRepository; s=SkillRepository().load_skill('recap'); print('OK:', s.path)"
```

Expected: `OK: .cursor/skills/recap/SKILL.md`

**Step 5: Verify full test suite**

```bash
ruff check src/ tests/ .cursor/hooks/ && pytest tests/ src/ -v 2>&1 | tail -5
```

Expected: all passed, 0 failed.

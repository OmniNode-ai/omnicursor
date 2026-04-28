# Execute Plan Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan phase-by-phase.

**Goal:** Add `plan-review`, `plan-to-tickets`, and `execute_plan` skills to OmniCursor,
wire them together as an autonomous execution pipeline, upgrade `plan-ticket` to use Linear
MCP, and document Linear MCP setup for users.

**Architecture:** Skill Markdown files in `skills/` + Cursor rules in `.cursor/rules/`.
`execute_plan` orchestrates: plan-review → plan-to-tickets (Linear) → per-ticket implementation.
No new Python models — skills are LLM-instruction documents only.

**Tech Stack:** Markdown (skill files), JSON (Cursor rules), Python (compliance.py + tests)

---

## Known Types Inventory

> Types relevant to this plan discovered in the repository.

- `ComplianceResult` — `src/omnicursor/schemas.py:27` — skill compliance check output
- `SkillDocument` — `src/omnicursor/schemas.py:19` — loaded skill metadata
- `COMPLIANCE_REGISTRY` — `src/omnicursor/compliance.py` — dict mapping skill name → checks

No new types are introduced by this plan. All additions are Markdown skill files and
compliance registry entries (plain dicts).

---

## Task 1: Configure Linear MCP setup instructions

**Files:**
- Modify: `docs/QUICKSTART.md`

**Step 1: Add Linear MCP setup section to QUICKSTART.md**

Add a new section after the "Quick Start" install section:

```markdown
## Linear MCP Setup (for plan-to-tickets and execute_plan)

1. Get your Linear API key: Linear → Settings → API → Personal API Keys
2. Edit `~/.cursor/mcp.json` (create if missing):

```json
{
  "mcpServers": {
    "linear": {
      "command": "npx",
      "args": ["-y", "@linear/mcp-server"],
      "env": {
        "LINEAR_API_KEY": "lin_api_XXXX"
      }
    }
  }
}
```

3. Restart Cursor — the `tracker.*` MCP tools become available.
4. Verify: open a Cursor chat and ask "list my Linear teams" — it should return your teams.
```

**Step 2: Verify QUICKSTART.md renders correctly**

Run: `cat docs/QUICKSTART.md | grep -A 20 "Linear MCP"`
Expected: section present with the json block and 4 steps

**Step 3: Commit**

```bash
git add docs/QUICKSTART.md
git commit -m "docs: add Linear MCP setup instructions to QUICKSTART"
```

**Acceptance criteria:**
- `docs/QUICKSTART.md` contains a "Linear MCP Setup" heading
- The JSON block shows the correct MCP server config
- No other sections modified

---

## Task 2: Upgrade plan-ticket skill to use Linear MCP

**Files:**
- Modify: `skills/plan-ticket.md`
- Modify: `.cursor/rules/12-plan-ticket.mdc`

**Step 1: Read current plan-ticket skill**

Run: `cat skills/plan-ticket.md`

**Step 2: Rewrite plan-ticket skill to call tracker.create_issue**

Replace the "Hand off" step and the "Expected Output Format" with:

```markdown
## Linear Ticket Creation (via MCP)

After generating the YAML template, create the ticket in Linear:

```
tracker.create_issue(
  title="<imperative title>",
  teamId="<team id from tracker.list_teams>",
  description="<requirements + verification as markdown>",
)
```

1. Call `tracker.list_teams` to get available teams.
2. Ask the user which team if multiple exist (or use the one matching the detected repo).
3. Call `tracker.create_issue` with the title and description derived from the YAML template.
4. Report the created ticket URL.
```

Remove the "Stage 2 ticket creation" handoff line since the skill now does it directly.

**Step 3: Update compliance entry for plan-ticket**

In `src/omnicursor/compliance.py`, update the `plan-ticket` entry:

```python
"plan-ticket": [
    ("detects_repo", [
        "omniclaude", "omnibase_core", "omnibase_infra", "omnidash",
        "omniintelligence", "omnimemory", "omninode_infra", "repo",
    ]),
    ("outputs_yaml_template", [
        "yaml", "title:", "repo:", "requirements:", "verification:",
        "template", "contract",
    ]),
    ("has_requirements_section", [
        "requirement", "r1", "statement", "rationale", "acceptance",
    ]),
    ("has_verification_section", [
        "verification", "pytest", "lint", "ruff", "mypy",
        "unit_test", "unit test", "blocking",
    ]),
    ("creates_linear_ticket", [
        "tracker.create_issue", "linear", "ticket", "created", "url",
    ]),
],
```

**Step 4: Run compliance test**

Run: `pytest tests/test_compliance.py::test_plan_ticket_compliance -v`
Expected: PASS (existing test uses keywords that still match)

**Step 5: Commit**

```bash
git add skills/plan-ticket.md .cursor/rules/12-plan-ticket.mdc src/omnicursor/compliance.py
git commit -m "feat: upgrade plan-ticket skill to create Linear tickets via MCP"
```

**Acceptance criteria:**
- `skills/plan-ticket.md` contains `tracker.create_issue` call instructions
- `tracker.list_teams` step is documented
- Compliance entry has `creates_linear_ticket` check
- `pytest tests/test_compliance.py::test_plan_ticket_compliance -v` passes

---

## Task 3: Create plan-review skill

**Files:**
- Create: `skills/plan-review.md`
- Create: `.cursor/skills/plan-review/SKILL.md`
- Create: `.cursor/rules/17-plan-review.mdc`

**Step 1: Write the failing compliance test**

Add to `tests/test_compliance.py`:

```python
def test_plan_review_fully_compliant() -> None:
    summary = (
        "Checking plan file docs/plans/my-plan.md. "
        "Count integrity: 5 tasks found, prose says 5. Pass. "
        "Acceptance criteria: all criteria are testable. Pass. "
        "Verdict: PASS — no critical or major findings."
    )
    result = check_compliance("plan-review", summary)
    assert result.compliant is True
    assert result.missing == []


def test_plan_review_missing_verdict() -> None:
    summary = (
        "Checking count integrity and acceptance criteria. "
        "Found 3 tasks. Criteria look testable."
    )
    result = check_compliance("plan-review", summary)
    assert result.compliant is False
    assert "states_verdict" in result.missing
```

**Step 2: Run test to confirm failure**

Run: `pytest tests/test_compliance.py::test_plan_review_fully_compliant -v`
Expected: FAIL — `no_registry_entry_for_plan-review` in missing

**Step 3: Add plan-review to COMPLIANCE_REGISTRY**

In `src/omnicursor/compliance.py`, add after the `"recap"` entry:

```python
"plan-review": [
    ("checks_count_integrity", ["count", "task", "numeric", "found", "prose"]),
    ("checks_acceptance_criteria", ["acceptance", "criteria", "testable", "vague"]),
    ("states_verdict", ["verdict", "pass", "fail", "critical", "major"]),
],
```

**Step 4: Run test to confirm pass**

Run: `pytest tests/test_compliance.py::test_plan_review_fully_compliant tests/test_compliance.py::test_plan_review_missing_verdict -v`
Expected: both PASS

**Step 5: Write skills/plan-review.md**

```markdown
# Plan Review

Adversarial pre-execution check on a plan file. Run this before execute_plan or manually.

**Announce at start:** "I'm using the plan-review skill."

## When to Use

Before executing a plan — either called automatically by execute_plan or invoked directly:

```
/plan-review docs/plans/my-plan.md
```

## Checks (R1–R6)

Run all six checks. Classify each finding: CRITICAL, MAJOR, MINOR, NIT.

### R1 — Count Integrity
Scan numeric claims near "tasks", "steps", "phases". Recount from actual `## Task N:` headings.
If count claim ≠ actual count: CRITICAL.

### R2 — Acceptance Criteria Strength
For each task's acceptance criteria:
- Ban subjective language: "clean", "robust", "nice" → MAJOR unless paired with measurable check
- Weak verification ("tests pass") without specific assertion → MAJOR
- "superset of N" without listing exact N → MINOR

### R3 — Scope Violations
Can the task's stated scope implement everything it claims?
- DB-only task claiming Python runtime guards → MAJOR
- Doc-only task claiming runtime enforcement → MAJOR

### R4 — Integration Traps
- New import paths: confirm module exists in repo
- API signatures: pin to actual call site, not assumed
- Return types: state actual path or shape

### R5 — Idempotency
Tasks that create resources must state dedup mechanism:
- Files: check existence before writing
- Tickets: dedup by title match
Missing dedup for resource-creating task → MINOR

### R6 — Verification Soundness
Grade each verification step:
- **strong**: schema introspection + rollback + runtime call
- **medium**: asserts specific fields or types
- **weak**: log contains string, file exists, command exits 0

Weak-only proof for core invariant → MAJOR. Pair with medium or strong.

## Verdict

After all checks:
- No CRITICAL/MAJOR → **PASS** (execute_plan may proceed)
- Any CRITICAL/MAJOR → **FAIL** (list findings, stop execution)

Output:
```
Plan Review: docs/plans/my-plan.md
R1: PASS  R2: PASS  R3: PASS  R4: MINOR  R5: PASS  R6: PASS
Findings: 0 CRITICAL, 0 MAJOR, 1 MINOR, 0 NIT
Verdict: PASS
```
```

**Step 6: Copy skill to .cursor/skills/plan-review/SKILL.md**

```bash
mkdir -p .cursor/skills/plan-review
cp skills/plan-review.md .cursor/skills/plan-review/SKILL.md
```

**Step 7: Write .cursor/rules/17-plan-review.mdc**

```json
---
description: Plan review — adversarial pre-execution check on a plan file
globs:
alwaysApply: false
---

When the user says `/plan-review` or "review plan" or "check plan":

Read the plan file at the path provided. Then follow `skills/plan-review.md` exactly.
```

**Step 8: Update test_all_skills_have_registry_entries**

In `tests/test_compliance.py`, add `"plan-review"` to the expected set:
```python
expected = {
    ...,
    "plan-review",
}
```

**Step 9: Run all compliance tests**

Run: `pytest tests/test_compliance.py -v`
Expected: all PASS

**Step 10: Commit**

```bash
git add skills/plan-review.md .cursor/skills/plan-review/SKILL.md \
    .cursor/rules/17-plan-review.mdc src/omnicursor/compliance.py \
    tests/test_compliance.py
git commit -m "feat: add plan-review skill with R1-R6 adversarial checks"
```

**Acceptance criteria:**
- `skills/plan-review.md` exists with R1–R6 checks documented
- `.cursor/skills/plan-review/SKILL.md` is identical copy
- `.cursor/rules/17-plan-review.mdc` exists
- `COMPLIANCE_REGISTRY["plan-review"]` has 3 checks
- All compliance tests pass

---

## Task 4: Create plan-to-tickets skill

**Files:**
- Create: `skills/plan-to-tickets.md`
- Create: `.cursor/skills/plan-to-tickets/SKILL.md`
- Create: `.cursor/rules/16-plan-to-tickets.mdc`

**Step 1: Write failing compliance test**

Add to `tests/test_compliance.py`:

```python
def test_plan_to_tickets_fully_compliant() -> None:
    summary = (
        "Parsing plan file docs/plans/my-plan.md. "
        "Found 5 task sections (## Task N: headings). "
        "Created Linear epic: OMN-100. "
        "Created tickets: OMN-101, OMN-102, OMN-103, OMN-104, OMN-105. "
        "Ticket IDs returned to caller."
    )
    result = check_compliance("plan-to-tickets", summary)
    assert result.compliant is True
    assert result.missing == []


def test_plan_to_tickets_missing_epic() -> None:
    summary = (
        "Parsing plan file. Found 3 tasks. "
        "Created tickets: OMN-1, OMN-2, OMN-3."
    )
    result = check_compliance("plan-to-tickets", summary)
    assert result.compliant is False
    assert "creates_epic" in result.missing
```

**Step 2: Run test to confirm failure**

Run: `pytest tests/test_compliance.py::test_plan_to_tickets_fully_compliant -v`
Expected: FAIL

**Step 3: Add plan-to-tickets to COMPLIANCE_REGISTRY**

```python
"plan-to-tickets": [
    ("parses_task_sections", ["task", "## task", "heading", "section", "found"]),
    ("creates_epic", ["epic", "parent", "OMN-"]),
    ("returns_ticket_ids", ["ticket", "linear", "created", "OMN-", "id"]),
],
```

**Step 4: Run test to confirm pass**

Run: `pytest tests/test_compliance.py::test_plan_to_tickets_fully_compliant tests/test_compliance.py::test_plan_to_tickets_missing_epic -v`
Expected: both PASS

**Step 5: Write skills/plan-to-tickets.md**

```markdown
# Plan to Tickets

Parse a plan file and batch-create Linear tickets — one per `## Task N:` section.
Called automatically by execute_plan, or invoked directly.

**Announce at start:** "I'm using the plan-to-tickets skill."

## Usage

```
/plan-to-tickets docs/plans/my-plan.md [--dry-run] [--skip-existing]
```

## Flow

### 1. Parse task sections

Read the plan file. Find all `## Task N:` headings (H2 level). Each heading = one ticket.

Example plan structure:
```
## Task 1: Write failing test for webhook handler
## Task 2: Implement webhook handler
## Task 3: Add integration test
```
→ 3 tickets will be created.

### 2. Get Linear team

Call `tracker.list_teams`. If multiple teams, ask the user which to use.
Cache the team ID for all subsequent calls.

### 3. Create epic

Call `tracker.create_issue` with:
- `title`: plan filename without date prefix and `.md` (e.g., "Execute Plan Pipeline")
- `teamId`: from step 2
- `description`: first paragraph of the plan (Goal + Architecture lines)

Record the epic's ticket ID (e.g., `OMN-100`).

### 4. Create one ticket per task

For each `## Task N:` section:
- `title`: the task heading text (e.g., "Write failing test for webhook handler")
- `teamId`: from step 2
- `parentId`: epic ID from step 3
- `description`: full task body (Files, Steps, Acceptance criteria)
- `blockedBy`: parse "Depends on Task N" or "after Task N" notes in task body → list of earlier ticket IDs

If `--skip-existing`: call `tracker.search_issues(title=<title>, parentId=<epic>)` first.
If a matching ticket exists, skip creation and use its ID.

### 5. Return ticket IDs

Output a mapping:
```
Task 1 → OMN-101
Task 2 → OMN-102 (blocked by OMN-101)
Task 3 → OMN-103 (blocked by OMN-101, OMN-102)
```

Return this mapping to the caller (execute_plan uses it for ordered execution).

## Dry Run

With `--dry-run`: parse the plan and print what would be created, but make no MCP calls.

```
[dry-run] Would create epic: "Execute Plan Pipeline"
[dry-run] Would create 3 tickets:
  Task 1: Write failing test for webhook handler
  Task 2: Implement webhook handler (blocked by Task 1)
  Task 3: Add integration test (blocked by Task 1, Task 2)
```

## Error Handling

- If `tracker.list_teams` fails: stop and report "Linear MCP not available. See QUICKSTART.md."
- If a ticket creation fails: report the failure and continue with remaining tasks.
  Record failed tasks in the summary.
```

**Step 6: Copy to .cursor/skills/plan-to-tickets/SKILL.md**

```bash
mkdir -p .cursor/skills/plan-to-tickets
cp skills/plan-to-tickets.md .cursor/skills/plan-to-tickets/SKILL.md
```

**Step 7: Write .cursor/rules/16-plan-to-tickets.mdc**

```
---
description: Plan to tickets — parse a plan file and create Linear tickets
globs:
alwaysApply: false
---

When the user says `/plan-to-tickets` or "create tickets from plan" or "tickets from plan":

Read the plan file at the path provided. Then follow `skills/plan-to-tickets.md` exactly.
```

**Step 8: Update test_all_skills_have_registry_entries**

Add `"plan-to-tickets"` to expected set.

**Step 9: Run all compliance tests**

Run: `pytest tests/test_compliance.py -v`
Expected: all PASS

**Step 10: Commit**

```bash
git add skills/plan-to-tickets.md .cursor/skills/plan-to-tickets/SKILL.md \
    .cursor/rules/16-plan-to-tickets.mdc src/omnicursor/compliance.py \
    tests/test_compliance.py
git commit -m "feat: add plan-to-tickets skill for batch Linear ticket creation"
```

**Acceptance criteria:**
- `skills/plan-to-tickets.md` exists with full flow documented
- `.cursor/rules/16-plan-to-tickets.mdc` triggers on `/plan-to-tickets`
- `COMPLIANCE_REGISTRY["plan-to-tickets"]` has 3 checks
- All compliance tests pass

---

## Task 5: Create execute-plan skill

**Files:**
- Create: `skills/execute-plan.md`
- Create: `.cursor/skills/execute-plan/SKILL.md`
- Create: `.cursor/rules/19-execute-plan.mdc`

**Step 1: Write failing compliance test**

Add to `tests/test_compliance.py`:

```python
def test_execute_plan_fully_compliant() -> None:
    summary = (
        "Running execute_plan on docs/plans/my-plan.md. "
        "plan-review: PASS. "
        "plan-to-tickets: created 3 tickets (OMN-101, OMN-102, OMN-103). "
        "Implemented ticket OMN-101: passed. "
        "Implemented ticket OMN-102: passed. "
        "Implemented ticket OMN-103: blocked after 2 fix attempts. "
        "Summary: 2 passed, 1 blocked, 0 skipped."
    )
    result = check_compliance("execute-plan", summary)
    assert result.compliant is True
    assert result.missing == []


def test_execute_plan_missing_summary() -> None:
    summary = (
        "Running plan-review: PASS. "
        "Created tickets via plan-to-tickets."
    )
    result = check_compliance("execute-plan", summary)
    assert result.compliant is False
    assert "reports_summary" in result.missing
```

**Step 2: Run test to confirm failure**

Run: `pytest tests/test_compliance.py::test_execute_plan_fully_compliant -v`
Expected: FAIL

**Step 3: Add execute-plan to COMPLIANCE_REGISTRY**

```python
"execute-plan": [
    ("calls_plan_review", ["plan-review", "review", "r1", "r2", "verdict"]),
    ("calls_plan_to_tickets", ["plan-to-tickets", "ticket", "linear", "epic", "OMN-"]),
    ("reports_summary", ["passed", "blocked", "skipped", "summary"]),
],
```

**Step 4: Run test to confirm pass**

Run: `pytest tests/test_compliance.py::test_execute_plan_fully_compliant tests/test_compliance.py::test_execute_plan_missing_summary -v`
Expected: both PASS

**Step 5: Write skills/execute-plan.md**

```markdown
# Execute Plan

Autonomous implementation pipeline. Reads a plan file, reviews it adversarially,
creates Linear tickets, and implements each ticket in order.

**Announce at start:** "I'm using the execute-plan skill."

## Usage

```
/execute_plan docs/plans/my-plan.md
```

## Pipeline

### Step 1: Plan Review

Follow `skills/plan-review.md` on the plan file.

- If verdict is **FAIL** (CRITICAL or MAJOR findings): stop. Report findings. Do not proceed.
- If verdict is **PASS**: continue to Step 2.

### Step 2: Create Linear Tickets

Follow `skills/plan-to-tickets.md` on the plan file.

- Creates one Linear epic + one ticket per `## Task N:` section.
- Records the mapping: Task N → ticket ID.
- If Linear MCP is unavailable: stop. Report "Linear MCP not configured. See QUICKSTART.md."

### Step 3: Implement Each Ticket

For each ticket in task order (respecting `blockedBy` dependencies):

**3a. Read the ticket**

Read the task description: files to create/modify, steps, acceptance criteria.

**3b. Implement**

Follow the task steps exactly:
- Write failing tests first (TDD)
- Implement minimal code to pass
- Run the tests

**3c. On test failure: attempt fix**

If tests fail after implementation:
- Attempt 1: follow `skills/systematic-debugging.md` — trace root cause, apply fix, re-run
- Attempt 2: if still failing, apply one more targeted fix

If still failing after 2 attempts:
- Mark ticket as **blocked** in Linear: `tracker.update_issue(id, state="blocked")`
- Add a comment with what was tried
- Continue to next ticket

**3d. On success**

Mark ticket as **done**: `tracker.update_issue(id, state="done")`

### Step 4: Report Summary

After all tickets are processed:

```
execute_plan summary: docs/plans/my-plan.md
  Passed:  N tickets (OMN-101, OMN-102)
  Blocked: N tickets (OMN-103 — 2 fix attempts exhausted)
  Skipped: N tickets (OMN-104 — blocked by OMN-103)

Next steps:
  - Review blocked tickets manually
  - Re-run `/execute_plan` after fixing blockers
```

## Failure Modes

| Condition | Action |
|-----------|--------|
| plan-review returns FAIL | Stop before creating any tickets |
| Linear MCP unavailable | Stop before creating any tickets |
| Ticket creation fails | Report, continue with remaining tasks |
| Implementation fails after 2 attempts | Mark blocked, continue to next ticket |
| Dependency not met (prior ticket blocked) | Mark as skipped, continue |
```

**Step 6: Copy to .cursor/skills/execute-plan/SKILL.md**

```bash
mkdir -p .cursor/skills/execute-plan
cp skills/execute-plan.md .cursor/skills/execute-plan/SKILL.md
```

**Step 7: Write .cursor/rules/19-execute-plan.mdc**

```
---
description: Execute plan — autonomous plan review, ticket creation, and implementation
globs:
alwaysApply: false
---

When the user says `/execute_plan` or "execute plan" or "run plan" or "implement plan":

Read the plan file at the path provided. Then follow `skills/execute-plan.md` exactly.
```

**Step 8: Update test_all_skills_have_registry_entries**

Add `"execute-plan"` to expected set.

**Step 9: Run full test suite**

Run: `pytest tests/ -v`
Expected: all PASS

Run: `ruff check src/ tests/ .cursor/hooks/`
Expected: no errors

**Step 10: Commit**

```bash
git add skills/execute-plan.md .cursor/skills/execute-plan/SKILL.md \
    .cursor/rules/19-execute-plan.mdc src/omnicursor/compliance.py \
    tests/test_compliance.py
git commit -m "feat: add execute-plan skill — autonomous pipeline orchestrator"
```

**Acceptance criteria:**
- `skills/execute-plan.md` exists with full 4-step pipeline
- Rule triggers on `/execute_plan`, "execute plan", "implement plan"
- `COMPLIANCE_REGISTRY["execute-plan"]` has 3 checks
- Full test suite passes with no ruff errors

---

## Task 6: Update skills test and run full CI check

**Files:**
- Modify: `tests/test_skills.py`

**Step 1: Read current test_skills.py**

Run: `cat tests/test_skills.py`

**Step 2: Add new skills to expected list**

In `test_available_skills_lists_all`, add `"plan-review"`, `"plan-to-tickets"`, `"execute-plan"`
to the expected skill list.

Add load tests:

```python
def test_load_plan_review_skill(repo: SkillRepository) -> None:
    doc = repo.load_skill("plan-review")
    assert doc is not None
    assert doc.path == ".cursor/skills/plan-review/SKILL.md"


def test_load_plan_to_tickets_skill(repo: SkillRepository) -> None:
    doc = repo.load_skill("plan-to-tickets")
    assert doc is not None
    assert doc.path == ".cursor/skills/plan-to-tickets/SKILL.md"


def test_load_execute_plan_skill(repo: SkillRepository) -> None:
    doc = repo.load_skill("execute-plan")
    assert doc is not None
    assert doc.path == ".cursor/skills/execute-plan/SKILL.md"
```

**Step 3: Run tests**

Run: `pytest tests/test_skills.py -v`
Expected: all PASS

**Step 4: Run full CI check**

Run: `pytest tests/ -v && ruff check src/ tests/ .cursor/hooks/`
Expected: all PASS, no ruff errors

**Step 5: Commit**

```bash
git add tests/test_skills.py
git commit -m "test: add skill load tests for plan-review, plan-to-tickets, execute-plan"
```

**Acceptance criteria:**
- `test_available_skills_lists_all` includes all 3 new skill names
- 3 new `test_load_*_skill` tests pass
- Full `pytest tests/ -v` passes
- `ruff check` passes

# Execute Plan Pipeline — Design

**Date:** 2026-04-26

## Overview

Full pipeline for autonomous plan execution in OmniCursor, mirroring OmniClaude's
`design-to-plan → executing-plans → plan-to-tickets → ticket-work` flow.

```
brainstorming → writing-plans → plan-review → execute_plan
                                                    ↓
                                        plan-to-tickets (Linear tickets)
                                                    ↓
                                        implement each ticket in order
```

---

## Components

### 1. Linear MCP Setup

Configure `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "linear": {
      "command": "npx",
      "args": ["-y", "@linear/mcp-server"],
      "env": {
        "LINEAR_API_KEY": "<your-key>"
      }
    }
  }
}
```

MCP tools used: `tracker.create_issue`, `tracker.list_teams`, `tracker.get_issue`,
`tracker.update_issue`.

---

### 2. plan-review skill

Adversarial pre-execution check on a plan file before any tickets are created.

**Checks (R1–R6):**
- R1: Count integrity — numeric claims match actual task count
- R2: Acceptance criteria strength — no vague/subjective criteria
- R3: Scope violations — each task's scope matches its claims
- R4: Integration traps — import paths, API signatures confirmed
- R5: Idempotency — tasks state dedup/rerun behavior
- R6: Verification soundness — each verification step has sufficient proof grade

**Output:** PASS (proceed) or FAIL with list of findings. CRITICAL/MAJOR → stop execution.

**Trigger:** `/plan-review docs/plans/my-plan.md`

---

### 3. plan-to-tickets skill

Parses a plan file and batch-creates Linear tickets — one per `## Task N:` section.

**Flow:**
1. Parse plan file for `## Task N:` headings
2. Create one Linear epic named after the plan
3. For each task: `tracker.create_issue(title, team, description, parentId=epic_id)`
4. Parse dependency notes in task body → `blockedBy` linking
5. Return list of `(task_N, ticket_id)` pairs

**Flags:** `--dry-run` (preview only), `--skip-existing` (dedup by title match under epic)

**Trigger:** `/plan-to-tickets docs/plans/my-plan.md [--dry-run]`

---

### 4. execute_plan skill

Top-level orchestrator. Input: path to a plan markdown file.

**Flow:**
1. **plan-review** → if CRITICAL/MAJOR findings: stop and report
2. **plan-to-tickets** → batch-create Linear tickets, receive ticket IDs
3. **For each ticket in order:**
   - Read task description from ticket
   - Implement: edit files, run tests
   - On test failure: attempt fix up to 2 times using `systematic-debugging`
   - If still failing after 2 attempts: mark ticket blocked, continue to next
4. **Report:** summary of passed / blocked / skipped tickets

**On failure behavior:** continue to next ticket (not stop-on-first-failure).

**Trigger:** `/execute_plan docs/plans/my-plan.md`

---

### 5. plan-ticket upgrade

Upgrade existing `plan-ticket` skill to call `tracker.create_issue()` via Linear MCP
instead of generating YAML output. This makes it consistent with `plan-to-tickets`.

---

## New Files

| File | Purpose |
|------|---------|
| `skills/plan-review.md` | plan-review skill instructions |
| `skills/plan-to-tickets.md` | plan-to-tickets skill instructions |
| `skills/execute-plan.md` | execute_plan skill instructions |
| `.cursor/rules/16-plan-to-tickets.mdc` | Cursor rule — triggers on `/plan-to-tickets` |
| `.cursor/rules/17-plan-review.mdc` | Cursor rule — triggers on `/plan-review` |
| `.cursor/rules/19-execute-plan.mdc` | Cursor rule — triggers on `/execute_plan` |
| `src/omnicursor/compliance.py` | Add entries for 3 new skills |
| `tests/test_compliance.py` | Tests for new compliance entries |
| `docs/QUICKSTART.md` | Update with Linear MCP setup instructions |

---

## Compliance Registry Entries

```python
"plan-review": [
    ("checks_count_integrity", ["count", "task", "numeric"]),
    ("checks_acceptance_criteria", ["acceptance", "criteria", "vague"]),
    ("states_verdict", ["pass", "fail", "critical", "major"]),
],
"plan-to-tickets": [
    ("parses_task_sections", ["task", "## task"]),
    ("creates_epic", ["epic"]),
    ("returns_ticket_ids", ["ticket", "linear"]),
],
"execute_plan": [
    ("calls_plan_review", ["plan-review", "review"]),
    ("calls_plan_to_tickets", ["plan-to-tickets", "ticket"]),
    ("reports_summary", ["passed", "blocked", "skipped"]),
],
```

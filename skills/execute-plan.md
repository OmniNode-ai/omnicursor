# Execute Plan

Autonomous implementation pipeline. Reads a plan file, reviews it adversarially,
creates Linear tickets, then implements each ticket in order.

**Announce at start:** "I'm using the execute-plan skill."

## Usage

```
/execute_plan docs/plans/my-plan.md
```

## Pipeline

### Step 1: Plan Review

Follow `skills/plan-review.md` on the plan file.

- If verdict is **FAIL** (any CRITICAL or MAJOR findings): stop. Report the findings. Do not create any tickets.
- If verdict is **PASS**: continue to Step 2.

### Step 2: Create Linear Tickets

Follow `skills/plan-to-tickets.md` on the plan file.

- Creates one Linear epic + one ticket per `## Task N:` section.
- Records the mapping: Task N → ticket ID.
- If Linear MCP is unavailable: stop and report "Linear MCP not configured. See QUICKSTART.md."

### Step 3: Implement Each Ticket

For each ticket in task order (respecting `blockedBy` dependencies):

**3a. Read the task**

Read the task description from the plan: files to create/modify, steps, acceptance criteria.

**3b. Implement**

Follow the task steps:
- Write failing tests first (TDD where applicable)
- Implement minimal code to pass
- Run the specified tests

**3c. On test failure — attempt fix**

If tests fail after implementation:
- Attempt 1: follow `skills/systematic-debugging.md` — trace root cause, apply fix, re-run tests
- Attempt 2: if still failing, apply one more targeted fix and re-run

If still failing after 2 attempts:
- Mark ticket **blocked** in Linear: `tracker.update_issue(id, state="blocked")`
- Add a comment with what was tried and where it failed
- Continue to next ticket

**3d. On success**

Mark ticket **done**: `tracker.update_issue(id, state="done")`
Continue to next ticket.

**3e. On dependency not met**

If a ticket's `blockedBy` dependency is itself blocked:
- Mark ticket **skipped**
- Continue to next ticket

### Step 4: Report Summary

After all tickets are processed:

```
execute_plan summary: docs/plans/my-plan.md
  Passed:  N tickets (OMN-101, OMN-102)
  Blocked: N tickets (OMN-103 — 2 fix attempts exhausted)
  Skipped: N tickets (OMN-104 — blocked by OMN-103)

Next steps:
  - Review blocked tickets and fix root cause manually
  - Re-run /execute_plan after resolving blockers
```

## Failure Modes

| Condition | Action |
|-----------|--------|
| plan-review returns FAIL | Stop before creating any tickets |
| Linear MCP unavailable | Stop before creating any tickets |
| Ticket creation fails | Report, continue with remaining tasks |
| Implementation fails after 2 attempts | Mark blocked, continue to next ticket |
| Dependency ticket is blocked | Mark dependent as skipped, continue |

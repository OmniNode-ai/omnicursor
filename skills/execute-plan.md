# onex:execute-plan

Autonomous implementation pipeline. Reads a plan file, reviews it adversarially,
creates Linear tickets, then runs the full ticket pipeline (implement → PR → CI → merge)
for each ticket via the Omnimarket bridge.

**Announce at start:** "I'm using the onex:execute-plan skill."

## Usage

```
/execute-plan docs/plans/my-plan.md
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

### Step 3: Run Ticket Pipeline for Each Ticket

For each ticket in task order (respecting `blockedBy` dependencies):

**3a. Via Omnimarket bridge (preferred)**

If the `omnicursor-omnimarket` MCP server is available, call:

```
run_ticket_pipeline(ticket_id="OMN-XX")
```

This drives the full pipeline unattended:
- IMPLEMENT → LOCAL_REVIEW → CREATE_PR → TEST_ITERATE → CI_WATCH → PR_REVIEW → AUTO_MERGE → DONE

On return, check `final_phase`:
- `done` → record pr_number, continue to next ticket
- `blocked` → note failure reason, continue to next ticket
- `failed` → note failure reason, continue to next ticket

**3b. Fallback — inline implementation (if bridge unavailable)**

If `run_ticket_pipeline` is not available:

1. Read the task description from the plan
2. Write failing tests first (TDD where applicable)
3. Implement minimal code to pass
4. Run tests — on failure, follow `skills/systematic-debugging.md` (max 2 attempts)
5. On success: push branch, open PR via `gh pr create`, mark ticket done in Linear
6. On failure after 2 attempts: mark ticket blocked, continue

**3c. On dependency not met**

If a ticket's `blockedBy` dependency is blocked or failed:
- Mark ticket **skipped**
- Continue to next ticket

### Step 4: Report Summary

After all tickets are processed:

```
execute-plan summary: docs/plans/my-plan.md
  Done:    N tickets (OMN-101 → PR #12, OMN-102 → PR #13)
  Blocked: N tickets (OMN-103 — pipeline failed: test_auth.py timeout)
  Skipped: N tickets (OMN-104 — blocked by OMN-103)

Next steps:
  - Review blocked tickets and fix root cause manually
  - Re-run /execute-plan after resolving blockers
```

## Failure Modes

| Condition | Action |
|-----------|--------|
| plan-review returns FAIL | Stop before creating any tickets |
| Linear MCP unavailable | Stop before creating any tickets |
| Ticket creation fails | Report, continue with remaining tasks |
| Bridge returns blocked/failed | Record reason, continue to next ticket |
| Inline fallback fails after 2 attempts | Mark blocked, continue to next ticket |
| Dependency ticket is blocked | Mark dependent as skipped, continue |

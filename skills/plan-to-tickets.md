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

Example:
```
## Task 1: Write failing test for webhook handler
## Task 2: Implement webhook handler
## Task 3: Add integration test
```
→ 3 tickets will be created.

### 2. Get Linear team

Call `tracker.list_teams`. If multiple teams exist, ask the user which to use.
Cache the team ID for all subsequent calls.

### 3. Create epic

Call `tracker.create_issue` with:
- `title`: plan filename without date prefix and `.md` suffix (e.g., "Execute Plan Pipeline")
- `teamId`: from step 2
- `description`: first paragraph of the plan (Goal + Architecture lines)

Record the epic's ticket ID (e.g., `OMN-100`).

### 4. Create one ticket per task

For each `## Task N:` section:
- `title`: the task heading text (e.g., "Write failing test for webhook handler")
- `teamId`: from step 2
- `parentId`: epic ID from step 3
- `description`: full task body (Files, Steps, Acceptance criteria)
- `blockedBy`: parse "Depends on Task N" or "after Task N" notes → list of earlier ticket IDs

With `--skip-existing`: search for an existing ticket with the same title under the same epic first.
If found, skip creation and use its ID.

### 5. Return ticket mapping

Output:
```
Epic: OMN-100
Task 1 → OMN-101
Task 2 → OMN-102 (blocked by OMN-101)
Task 3 → OMN-103 (blocked by OMN-101, OMN-102)
```

Return this mapping to the caller (execute_plan uses it for ordered implementation).

## Dry Run

With `--dry-run`: parse the plan and print what would be created, but make no MCP calls.

```
[dry-run] Would create parent epic: "Execute Plan Pipeline"
[dry-run] Would create 3 tickets:
  Task 1: Write failing test for webhook handler
  Task 2: Implement webhook handler (blocked by Task 1)
  Task 3: Add integration test (blocked by Task 1, Task 2)
```

## Error Handling

- If `tracker.list_teams` fails: stop and report "Linear MCP not available. See QUICKSTART.md Linear MCP Setup section."
- If a ticket creation fails: report the failure and continue with remaining tasks. Record failed tasks in the final summary.

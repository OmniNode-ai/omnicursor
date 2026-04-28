# Plan Review

Adversarial pre-execution check on a plan file. Run this before execute_plan or manually.

**Announce at start:** "I'm using the plan-review skill."

## Usage

```
/plan-review docs/plans/my-plan.md
```

## Checks (R1–R6)

Run all six checks. Classify each finding: CRITICAL, MAJOR, MINOR, NIT.

### R1 — Count Integrity

Scan numeric claims near "tasks", "steps", "phases". Recount from actual `## Task N:` headings.
If any count claim ≠ actual count: CRITICAL.

### R2 — Acceptance Criteria Strength

For each task's acceptance criteria:
- Ban subjective language: "clean", "robust", "nice" → MAJOR unless paired with a measurable check
- Weak verification ("tests pass") without specific assertion → MAJOR
- "superset of N" without listing exact N → MINOR

### R3 — Scope Violations

Can the task's stated scope implement everything it claims?
- DB-only task claiming Python runtime guards → MAJOR
- Doc-only task claiming runtime enforcement → MAJOR (unless doc is a confirmed runtime source)

### R4 — Integration Traps

- New import paths: confirm module exists in repo before referencing
- API signatures: pin to actual call site, not assumed shape
- Return types: state actual path or describe shape — not "returns ModelFoo" without a path

### R5 — Idempotency

Tasks that create resources must state dedup mechanism:
- Files: check existence before writing
- Tickets: dedup by title match
Missing dedup for a resource-creating task → MINOR.

### R6 — Verification Soundness

Grade each verification step:
- **strong**: schema introspection + rollback + runtime call
- **medium**: asserts specific fields or types
- **weak**: log contains string, file exists, command exits 0

Weak-only proof for a core invariant → MAJOR. Pair with medium or strong.

## Verdict

After all checks:
- No CRITICAL or MAJOR findings → **PASS** (execute_plan may proceed)
- Any CRITICAL or MAJOR → **FAIL** (list all findings, stop — do not proceed to ticket creation)

Output format:
```
Plan Review: docs/plans/my-plan.md
R1: PASS  R2: PASS  R3: PASS  R4: MINOR  R5: PASS  R6: PASS
Findings: 0 CRITICAL, 0 MAJOR, 1 MINOR, 0 NIT
Verdict: PASS
```

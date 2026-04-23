---
name: systematic-debugging
description: >-
  Find the smallest verified root cause before proposing a fix. Use when debugging failures, regressions, tracebacks, flaky tests, or any unexpected behavior.
---

# Systematic Debugging

Use this skill when the user is debugging a failure, regression, flaky behavior, traceback, or unclear root cause.

## Goal

Find the smallest verified explanation for the problem before proposing a fix.

## Workflow

1. Capture the symptom.
   Record the exact error, failing test, unexpected behavior, and what should have happened instead.
2. Reproduce the issue.
   Prefer the smallest deterministic command, test, or input that shows the failure.
3. Bound the search area.
   Narrow the problem to one component, one code path, or one recent change before editing.
4. Form a short hypothesis list.
   Keep it to one to three plausible causes based on evidence.
5. Test one hypothesis at a time.
   Change one variable, collect evidence, and discard the hypothesis if the evidence does not support it.
6. Apply the smallest fix.
   Avoid unrelated cleanup while the root cause is still being verified.
7. Verify twice.
   Run the narrowest reproducer first, then run the next broader verification that could catch regressions.

## Guardrails

- Do not guess at root cause without evidence.
- Do not redesign the system if a local fix solves the observed bug.
- If the issue is really a new feature or design change, hand off to `10-brainstorming`.
- If the fix becomes a multi-step implementation effort, hand off to `11-writing-plans`.

## Response Shape

When you finish, summarize:

- symptom
- root cause
- evidence
- fix
- verification
- follow-up risks

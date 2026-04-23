---
name: handoff
description: >-
  Capture current session context, progress, and next steps into a handoff doc. Use at the end of a session or before switching tasks to preserve continuity.
---

# Handoff

Use this skill when ending a session and you want the next session to pick up where you left off. The goal is to capture enough context for seamless session continuity.

## Purpose

Sessions end for many reasons — context limits, breaks, or task switches. Without an explicit handoff, the next session starts cold and wastes time rediscovering state. This skill captures the current working context into a structured manifest so the next session can resume efficiently.

## Prerequisites

- An active working session with progress worth preserving
- Understanding of what was accomplished and what remains

## Workflow

1. **Capture current state.**
   Record the essential context:
   - Current branch and recent commits (last 3-5).
   - Files actively being modified.
   - Active ticket or task identifier, if any.
   - Test status (passing, failing, not yet run).

2. **Summarize progress.**
   Write a brief summary of what was accomplished in this session. Focus on decisions made, approaches chosen, and any non-obvious context that would be lost.

3. **Document remaining work.**
   List what still needs to be done, in order. Be specific — "implement the validation layer in auth.py" is useful; "finish the feature" is not.

4. **Note blockers and warnings.**
   Record anything the next session should know: failing tests with known causes, environment issues, dependencies on external work, or decisions that need user input.

5. **Write the handoff manifest.**
   Save to a **session-specific path** such as `docs/dev/handoffs/YYYY-MM-DD-<short-slug>.md` or `docs/plans/YYYY-MM-DD-session-handoff.md`. Prefer **not** overwriting `docs/dev/HANDOFF.md` unless the user explicitly asks — that file is often the team's long-lived continuity doc. The manifest should be self-contained — a reader with access to the repo but no prior context should understand what to do next.

## Expected Output Format

A handoff document containing:
- Session summary (what was done)
- Current state (branch, recent commits, modified files)
- Remaining tasks (ordered, specific)
- Blockers and warnings
- Suggested first action for the next session

## Quality Checklist

- [ ] Branch and recent commits are recorded
- [ ] Summary describes what was accomplished, not just what was touched
- [ ] Remaining tasks are specific and ordered
- [ ] Blockers are noted with enough context to act on
- [ ] The handoff is self-contained for a cold-start reader

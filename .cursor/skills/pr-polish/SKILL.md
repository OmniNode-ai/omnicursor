---
name: pr-polish
description: >-
  Resolve merge conflicts and address reviewer comments to get a PR ready to merge. Use when a PR has outstanding review feedback or conflicts.
---

# PR Polish

Use this skill when a PR exists but is not yet merge-ready. The goal is to take an open PR through conflict resolution, review feedback, and iterative quality passes until it is clean enough to merge.

## Purpose

Bring an existing PR from "open with issues" to "merge-ready" through a structured three-phase workflow. This prevents the common pattern of fixing one issue while introducing another.

## Prerequisites

- An open PR (number or current branch)
- Access to `gh` CLI for PR data and pushing

## Workflow

1. **Resolve merge conflicts (Phase 0).**
   Run `git status` to check for unmerged paths. If conflicts exist, resolve each file by reading both sides, choosing the correct resolution, then staging and committing. Skip this phase if no conflicts are found.

2. **Address review comments and CI failures (Phase 1).**
   Fetch all open review comments with `gh pr view <number> --json reviews,reviewThreads`. For each unresolved thread:
   - If actionable: implement the fix, commit, then reply explaining what changed.
   - If not applicable: reply with a specific reason, then resolve.
   Never resolve a thread without posting a reply.
   Check CI status and fix any failing checks (lint first, then type errors, then test failures).

3. **Iterative local review (Phase 2).**
   Review the full diff yourself. Fix any CRITICAL, MAJOR, or MINOR issues found. Re-review after fixing. Repeat until two consecutive passes find nothing above NIT severity. Cap at 10 iterations to prevent infinite loops.

4. **Push and report.**
   Push all fixes. Report a summary of each phase: files resolved, issues fixed, iterations needed, and final merge readiness status.

## Expected Output Format

A phase-by-phase status report:
- Phase 0: conflict resolution result (skipped / N files resolved)
- Phase 1: review comments addressed (N fixed, M replied)
- Phase 2: local review passes (N iterations, converged / capped)
- Final verdict: merge-ready or remaining blockers

## Quality Checklist

- [ ] Merge conflicts resolved before addressing review comments
- [ ] Every review thread has a reply before being resolved
- [ ] CI failures are fixed in priority order (lint, types, tests)
- [ ] Local review iterated until two consecutive clean passes
- [ ] Final push includes all fixes from all phases

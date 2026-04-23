---
name: merge-planner
description: >-
  Determine safe PR merge order and surface integration conflicts before they happen. Use when multiple PRs are ready and merge sequencing matters.
---

# Merge Planner

Use this skill when multiple PRs target the same branch and you need to decide merge order, or when a PR has complex dependencies that affect merge safety. The goal is to classify PRs and produce a priority-ordered merge plan.

## Purpose

Merging PRs in the wrong order causes unnecessary conflicts, broken CI, and wasted rebase cycles. This skill provides a structured approach to classifying PRs by type, scoring their priority, and determining a safe merge sequence.

## Prerequisites

- Two or more open PRs targeting the same branch, or a single PR with dependency concerns
- Access to `gh` CLI for fetching PR metadata and CI status

## Workflow

1. **Classify each PR by type.**
   Read the diff summary and labels for each PR. Assign one type:
   - **Accelerator** — Small, self-contained changes (docs, config, typo fixes, dependency bumps) that cannot conflict with other PRs.
   - **Normal** — Feature work, bug fixes, or refactors that touch shared code.
   - **Blocked** — PRs with failing CI, unresolved review comments, or explicit dependency on another PR.

2. **Score priority across dimensions.**
   For each non-blocked PR, assess these dimensions:
   - **Size** — Smaller PRs merge first (less conflict surface).
   - **Age** — Older PRs get slight priority to prevent staleness.
   - **CI status** — Green CI scores higher than pending.
   - **Review status** — Approved PRs score higher than awaiting review.
   - **Conflict risk** — PRs touching fewer shared files score higher.

3. **Determine merge order.**
   Sort PRs by: accelerators first (they clear the queue), then normal PRs by priority score descending. For ties, prefer the older PR. List blocked PRs last with their blocking reason.

4. **Check for base branch conflicts.**
   For the top-priority PR, verify it can merge cleanly into the target branch. If conflicts exist, note which files conflict and whether a rebase is needed before merge.

5. **Output the merge plan.**
   Present the ordered list with: PR number, title, type, priority score, and any action required (merge, rebase first, or blocked — fix X).

## Expected Output Format

A merge plan containing:
- PR classification table (number, title, type, CI status, review status)
- Priority-ordered merge sequence with scores
- Blocked PRs with blocking reasons
- Conflict warnings for the next PR to merge

## Quality Checklist

- [ ] Every PR is classified as accelerator, normal, or blocked
- [ ] Priority scoring considers size, age, CI, review, and conflict risk
- [ ] Merge order lists accelerators before normal PRs
- [ ] Blocked PRs include a specific blocking reason
- [ ] Conflict check performed for the top-priority PR

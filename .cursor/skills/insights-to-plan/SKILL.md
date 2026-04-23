---
name: insights-to-plan
description: >-
  Parse code review findings or analysis output into categorized, prioritized tasks. Use when converting a review report into actionable implementation work.
---

# Insights to Plan

Use this skill when you have analysis results, review findings, or session insights that need to be converted into an actionable implementation plan. The goal is to transform observations into prioritized, executable tasks.

## Purpose

Insights without a plan decay. This skill takes unstructured findings — from code reviews, debugging sessions, performance analyses, or retrospectives — and produces a structured plan document ready for execution.

## Prerequisites

- A set of findings, observations, or insights (from a review, analysis, or report)
- Understanding of the project's current priorities

## Workflow

1. **Gather and categorize insights.**
   Collect all findings from the source material. Group them by category: friction points, quick wins, new capabilities, and deferred improvements. Discard observations that have no actionable follow-up.

2. **Assign priority bands.**
   Classify each actionable insight into one priority:
   - **P0** — Blocking issues or recurring friction that affects daily work.
   - **P1** — Quick wins that can be implemented immediately with high impact.
   - **P2** — New capabilities or workflow improvements worth building.
   - **P3** — Deferred improvements — valuable but not urgent.

3. **Write task blocks.**
   For each insight, produce a task block with:
   - **What to do** — A specific, actionable instruction (not a vague suggestion).
   - **Why** — The evidence or metric that justifies this task.
   - **Acceptance criteria** — An observable outcome that confirms the task is done.
   - **Files affected** — Known file paths, or "unknown" if discovery is needed.

4. **Order by priority and dependency.**
   List P0 tasks first, then P1, P2, P3. Within the same band, order by dependency — tasks that unblock others come first.

5. **Save the plan.**
   Write the plan to `docs/plans/YYYY-MM-DD-<topic>-plan.md` using today's date and a descriptive slug.

## Expected Output Format

A Markdown plan document containing:
- Executive summary (2-3 sentences on the source and top findings)
- Task blocks ordered by priority, each with: priority, what to do, why, acceptance criteria, files affected
- A count summary (e.g., P0=2, P1=3, P2=4, P3=1)

## Quality Checklist

- [ ] All insights are categorized, not just listed
- [ ] Every task has a specific action, not a vague suggestion
- [ ] Priority bands (P0-P3) are assigned consistently
- [ ] Each task includes acceptance criteria
- [ ] Plan is saved to `docs/plans/` with a dated filename
